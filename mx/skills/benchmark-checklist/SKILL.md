---
name: benchmark-checklist
description: "Vet a perf measurement (limiter, tuning, limits, errors, repeatability, relevance, and whether the work happened) before you report or act on it. Use when you run a benchmark or report a speedup or regression you measured."
---

# Benchmark checklist

Answer each question with evidence from a run, not a guess about the code.

For a quick ballpark the user asked for, one run is enough: check questions 4 and 7, say it is one run, and skip the rest unless the run looks wrong. A choice between options is never a ballpark.

## Before you run anything

- Write down the claim you expect to make, in the words you would ship ("export is 30% faster at p50 on the 60k-row dataset"). The questions test that sentence.
- Read the measurement script: what it times, counts and ignores.
- Check the load (`uptime`) and the cores (`nproc`). On a busy machine, find out what runs. If you cannot stop it, interleave the sides so both see the same noise, and say so in the report.

## The questions

1. **Why not double?** Name the limiter. Profile in a run you do not report, since profilers slow the work down: CPU per process (`top`, `pidstat`), a runtime profiler (`node --cpu-prof`, `py-spy`, `perf`), I/O wait, syscall counts (`strace -c`), then map the hot spot to source. Watch the load generator too: if it saturates first, you measured the load generator. A change that did not move the number has a limiter that explains why; find it before calling the change useless.
2. **Was it tuned?** Run every side the way production runs it: release builds, production flags and env, batching and transaction settings, connection pools, caches as warm or cold as production sees them, the same versions and data. One side on defaults compares configurations, not implementations. A limiter that is a setting (a commit per row, a debug build, a missing index) means that side is untuned: tune it and measure again before picking a winner, and pick none from a run you could not tune. Narrowing the claim to "the code as it ships today" does not fix this when the user is choosing what to adopt; they adopt the option, not today's settings.
3. **Did it break limits?** Do the arithmetic: bytes per second against disk and network bandwidth, operations per second times cost per operation against your cores, the time saved against the time the changed piece took. Removing a piece that takes 10% of the run makes it at most about 11% faster. A result past a limit measured something other than the work: a cache, a no-op, a bug.
4. **Did it error?** Count failures and non-success responses, and check that outputs are correct, not just present. Rejections are often fast; timeouts and retries are slow. A script that does not count errors gets the count added.
5. **Does it reproduce?** Run each side at least 5 times, alternating (A, B, A, B, …) so warmup, lazy initialization, caches and drift favor neither. Report the median and range. A gap smaller than the run-to-run variation is no measurable difference. On a close call, use a rank-sum test or the harness's own statistics.
6. **Does it matter?** Next to any micro result, measure the end-to-end path a user waits on, with realistic data sizes and concurrency, and report the micro result as a share of it. A helper that takes 1% of a request makes the request at most 1% faster, however fast the helper gets.
7. **Did it even happen?** Confirm the work ran inside the timed region: the request reached the server, the rows were written, the bytes were read, the code used the result. Lazy code (generators nobody iterates, promises nobody awaits, results the JIT discards) and timeouts produce numbers for work that never happened.

## Report

- Lead with the verdict: faster, slower, no measurable difference, or inconclusive.
- Give the number with its unit, the run count, the range and the limiter: "p50 41 ms → 33 ms, median of 7 runs per side, range 32 to 35 ms after, bound by JSON parsing on one core."
- The verdict is inconclusive when you claim a difference but cannot name the limiter, when a side ran untuned, or when you could not check questions 4 and 7. Name the gap.
- A PR body carries one primary number; the runs, range and limiter evidence go in a linked artifact or notes file.
