#!/usr/bin/env bash
# Claude Code status line: reads the session JSON on stdin, prints two rows.
#   row 1: session id │ [host] user in dir with model (effort) │ git │ session duration
#   row 2: label bar detail, for the context window and the 5h and weekly usage windows
# Input fields: https://code.claude.com/docs/en/statusline
input=$(cat)
now=$(date +%s)
D='\e[90m' N='\e[0m'

# \x1f separates the fields: a tab would collapse an empty field, like a missing effort.
IFS=$'\x1f' read -r sid model effort dir tp ctx_pct ctx_tokens h5 h5_reset wk wk_reset < <(jq -r '[
  (.session_id // ""),
  .model.display_name,
  (.effort.level // ""),
  (.workspace.current_dir | sub(".*/"; "")),
  (.transcript_path // ""),
  (.context_window.used_percentage // 0 | floor),
  (.context_window.total_input_tokens // 0),
  (.rate_limits.five_hour.used_percentage // -1 | floor),
  (.rate_limits.five_hour.resets_at // 0),
  (.rate_limits.seven_day.used_percentage // -1 | floor),
  (.rate_limits.seven_day.resets_at // 0)
] | map(tostring) | join("\u001f")' <<<"$input")

# Wall time from the transcript's first to last timestamped entry (metadata lines carry none).
duration() {
  [ -f "$tp" ] || return
  local t1 t2 s
  t1=$(grep -m1 '"timestamp":"' "$tp" | jq -r '.timestamp // empty' 2>/dev/null)
  t2=$(tail -50 "$tp" | grep '"timestamp":"' | tail -1 | jq -r '.timestamp // empty' 2>/dev/null)
  [ -n "$t1" ] && [ -n "$t2" ] || return
  s=$(( $(date -d "$t2" +%s) - $(date -d "$t1" +%s) ))
  if ((s >= 3600)); then echo "$((s / 3600))h$((s % 3600 / 60))m"
  elif ((s >= 60)); then echo "$((s / 60))m"
  else echo "<1m"; fi
}

# Branch, ahead/behind upstream, and staged/modified/untracked counts.
git_info() {
  local branch ab ahead behind div="" status counts=""
  branch=$(git --no-optional-locks branch --show-current 2>/dev/null)
  [ -n "$branch" ] || return
  local out=$branch
  if ab=$(git --no-optional-locks rev-list --left-right --count '@{u}...HEAD' 2>/dev/null); then
    read -r behind ahead <<<"$ab"
    ((ahead > 0)) && div="↑$ahead"
    ((behind > 0)) && div+="↓$behind"
    [ -n "$div" ] && out+=" $div"
  fi
  status=$(git --no-optional-locks status --porcelain 2>/dev/null)
  if [ -n "$status" ]; then
    local staged modified untracked
    staged=$(grep -c '^[MADRC]' <<<"$status")
    modified=$(grep -c '^.[MD]' <<<"$status")
    untracked=$(grep -c '^??' <<<"$status")
    ((staged > 0)) && counts="+$staged"
    ((modified > 0)) && counts+="${counts:+ }~$modified"
    ((untracked > 0)) && counts+="${counts:+ }?$untracked"
    [ -n "$counts" ] && out+=" $counts"
  fi
  echo "$out"
}

# Six-cell line bar in half-cell steps: ━ used, ╸ half, ─ left.
bar() {
  local pct=$1 colour=$2 halves full i out
  halves=$(( (pct * 12 + 50) / 100 )); ((halves > 12)) && halves=12
  full=$((halves / 2))
  out=$colour
  for ((i = 0; i < full; i++)); do out+="━"; done
  ((halves % 2)) && { out+="╸"; full=$((full + 1)); }
  out+=$D
  for ((i = full; i < 6; i++)); do out+="─"; done
  printf '%b' "$out$N"
}

# Colour by pace: green while usage trails the share of the window already elapsed.
pace_colour() {
  local used=$1 reset=$2 window=$3 elapsed
  elapsed=$(( (window - (reset - now)) * 100 / window ))
  if ((used <= elapsed)); then printf '\e[32m'
  elif ((used <= elapsed + 15)); then printf '\e[33m'
  else printf '\e[31m'; fi
}

until_reset() {
  local s=$(( $1 - now ))
  if ((s >= 86400)); then echo "$((s / 86400))d"
  elif ((s >= 3600)); then echo "$((s / 3600))h"
  else echo "$((s / 60))m"; fi
}

tokens() {
  if (($1 >= 1000000)); then awk -v t="$1" 'BEGIN { printf "%.1fM", t / 1e6 }'
  elif (($1 >= 1000)); then echo "$(($1 / 1000))k"
  else echo "$1"; fi
}

# Row 1
[ -n "$sid" ] && printf "$D%s │$N " "$sid"
printf "\e[36m[\e[37m%s\e[36m]$N \e[37m%s$N \e[32min$N \e[33;1m%s$N \e[32mwith$N \e[36m%s$N" \
  "$(hostname -s)" "$(whoami)" "$dir" "$model"
[ -n "$effort" ] && printf " $D(%s)$N" "$effort"
g=$(git_info); [ -n "$g" ] && printf " $D│$N \e[35m%s$N" "$g"
d=$(duration); [ -n "$d" ] && printf " $D│$N \e[37m%s$N" "$d"
echo

# Row 2
if ((ctx_pct < 50)); then c='\e[32m'; elif ((ctx_pct < 75)); then c='\e[33m'; else c='\e[31m'; fi
printf "${D}ctx$N $(bar "$ctx_pct" "$c") $D%s$N" "$(tokens "$ctx_tokens")"
((h5 >= 0)) && printf "   ${D}5h$N $(bar "$h5" "$(pace_colour "$h5" "$h5_reset" 18000)") $D↻%s$N" "$(until_reset "$h5_reset")"
((wk >= 0)) && printf "   ${D}week$N $(bar "$wk" "$(pace_colour "$wk" "$wk_reset" 604800)") $D↻%s$N" "$(until_reset "$wk_reset")"
echo
