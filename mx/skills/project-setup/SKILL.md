---
name: project-setup
description: Set up a project's foundations — new or existing. Use when starting a new project, adding tooling (Makefile, linting, flake) to an existing repo, making a repo dispatchable, or when a project lacks a reproducible install.
---

# Project setup

Target preferences for a project's foundations. On a fresh project, build all of it; on an existing repo, the user says what they want — ask where unclear, and the project's own instructions overrule anything here.

## Core

- **Reproducible install is the one hard requirement.** One documented command takes a clean checkout to a working environment — a worker on another machine runs it as the first thing in a fresh worktree. Everything else here is preference.
- **Make targets are the convention**: `install`, `check`, `test`, and where they apply `run`, `format`, `fix`, `release-patch|minor|major`. Agents and humans alike answer "how do I check this project" by reading the Makefile.
- **Git + GitHub**: init, sensible first commit, `gh repo create --private` (private always; the user makes things public themselves). The repo's `.gitignore` carries only project-specific entries — the global gitignore already covers editors, caches, and build junk.
- **MIT license** unless the user says otherwise.
- **README stub**: what it is, install, usage. No aspirational sections.
- **Flake rule**: a dependency the language package manager can't deliver (compiler, native lib, Postgres, ffmpeg, CUDA — for node projects, node and pnpm themselves) goes in a devShell flake, so every machine — including NixOS hosts — gets it from one pinned declaration. `nix develop -c <cmd>` runs a command inside it. Projects whose needs the language toolchain fully covers get no flake (uv delivers Python itself; npm delivers neither node nor pnpm, so node projects always get one).

  ```nix
  {
    inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    outputs = { self, nixpkgs }:
      let pkgs = nixpkgs.legacyPackages.x86_64-linux; in {
        devShells.x86_64-linux.default = pkgs.mkShell {
          packages = [ pkgs.ffmpeg ]; # the non-uv/npm deps, nothing else
        };
      };
  }
  ```

## Stacks

- Python → [PYTHON.md](PYTHON.md)
- Node/TypeScript → [NODE.md](NODE.md)
- Any other stack: apply the core; when a stack recurs across projects, its preferences become a sidecar file here.
