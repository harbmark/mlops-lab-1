# Lab 1

## Question 1 — What do the files created by `uv init` contain?

Running `uv init` creates the basic scaffolding for a Python project:

* **`pyproject.toml`** — project metadata: name, version, Python version requirement, and the dependency list. This is where `uv add pillow` later wrote `pillow>=12.3.0`.
* **`.python-version`** — pins the exact Python version `uv` will use for this project, so `uv run` always resolves to the same interpreter.
* **`README.md`** — empty scaffold for project documentation.
* **`src/mlops_lab_1/__init__.py`** — the `src`-layout package folder, where actual project code (like `food11/data.py`) goes.

`uv.lock` does **not** appear yet at this stage — it only gets generated once at least one dependency is added and resolved (it showed up after running `uv add pillow`).

**In simple terms:** `uv init` sets up an organized Python project skeleton; the lockfile and dependency list only fill in once you actually add a package.

---

## Question 2 — What files are created by `dvc init` and what should be pushed?

Running `dvc init` creates:

* **`.dvc/config`** — DVC's settings file (remote URL, default remote), initially empty until configured.
* **`.dvc/.gitignore`** — tells Git to ignore DVC's internal cache/tmp folders.
* **`.dvcignore`** — tells DVC which files/folders it should never track.
* **`.dvc/cache/`** — where DVC stores the actual tracked data locally (content-addressed by hash).
* **`.dvc/tmp/`** — DVC's internal scratch space (lock files, run logs).

**Should be pushed to Git:** `.dvc/config` (once it has the non-secret remote URL) and `.dvcignore` — small text files.

**Should never be pushed:** `.dvc/cache/` and `.dvc/tmp/` — local, potentially huge, machine-specific.

**In simple terms:** Git tracks dvc's small config/plumbing files; dvc's remote holds the actual bytes.

---

## Question 3 — Where are the credentials stored, and should they be pushed?

Using `--global` when running `dvc remote modify ... auth basic ... user ... password ...` stores the credentials **outside the repository entirely**, at the user/machine level (on Windows, roughly under the user's `AppData` folder for dvc's global config) — not inside `.dvc/config`.

**Other options besides `--global`:**

* **`--local`** (the default if no flag is given) — writes to `.dvc/config.local`, which is automatically added to `.dvc/.gitignore` so it's never committed by accident.
* **`--system`** — system-wide, affects every user on the machine.
* **No flag / project-level** — writes directly to `.dvc/config`, meant only for non-secret settings like the remote URL.

**Should credentials be pushed to GitHub?**

No — never. The remote **URL** is public/safe to commit (it's just an address), but the username/password/auth token must stay out of git entirely. This is exactly why dvc splits config into project-level (`.dvc/config`, safe) vs. global/local (credentials, excluded).

---

## Question 4 — What happened to `.gitignore`?

Running:

```
dvc add data
```

automatically appended:

```
/data
```

to `.gitignore` — without being asked. This means `git status` and `git add .` will now silently skip the entire `data/` folder forever, so a large binary dataset can never accidentally get committed straight into git history.

**In simple terms:** dvc tracks the actual dataset; git is told to never even look at it.

---

## Question 5 — What is the `.dvc` file?

Running `dvc add data` created `data.dvc`, containing:

```yaml
outs:
- md5: <hash>.dir
  size: <bytes>
  nfiles: <count>
  hash: md5
  path: data
```

* **`md5`** — a single combined hash of the entire directory's contents (a "directory manifest" hash). Change even one file inside, and this changes.
* **`size`** — total size in bytes of the real data, living only in dvc's cache/remote, never in git.
* **`nfiles`** — file count, useful as a sanity check.
* **`path`** — which folder this pointer resolves to.

This ~200-byte file is what git actually commits. Anyone who clones the repo gets this pointer for free via git, and can run `dvc pull` to fetch the real bytes from the remote — completely separate from git's own storage.

---

## Question 6 — GitHub Main Branch / DagsHub

**Is the code on GitHub?**
Yes — `src/`, `pyproject.toml`, `uv.lock`, `README.md`, `.python-version`, `.dvc/`, `.dvcignore`, `.gitignore` are all there.

**Is the data on GitHub?**
No — there is no `data/` folder at all in the GitHub file listing. Only `data.dvc` exists.

**Is there a file that points to the data?**
Yes — `data.dvc`.

**Is the data visible on DagsHub?**
Partially, with a wrinkle we actually hit: DagsHub's file browser showed the `data` folder with a **"Create dataset"** button instead of a normal file view — meaning DagsHub had received the pointer/hash structure, but hadn't rendered the underlying files into its browsable dataset viewer yet. `dvc status -c` confirmed cache and remote were "in sync," so the individual files were genuinely uploaded, even though DagsHub's UI didn't show them as a normal browsable folder.

**In simple terms:**
**GitHub → code + `data.dvc` pointer only**
**DagsHub → actual dataset bytes (though the web UI's dataset browser needed an explicit "Create dataset" step to display them)**

---

## Question 7 — Fresh Clone

**Do we see the `data/` folder after cloning?**

No. Cloning the repo into a brand-new folder produced an 11.30 KiB clone with **no `data` directory at all** — confirming git never touched the actual images, only the code and the tiny `data.dvc` pointer.

**How do we get the data?**

`dvc pull` is the command meant to read `data.dvc` and fetch the matching files from the remote.

**A real issue we ran into:** in our case, `dvc pull` on the fresh clone actually **failed** with a missing directory-manifest error (`WARNING: Some of the cache files do not exist neither locally nor on remote`), even though `dvc status -c` on the original machine said everything was in sync. This traced back to earlier `dvc push` attempts that failed with heavy connection errors (`Server disconnected`, `semaphore timeout`) under default parallelism — later pushes with reduced/scoped jobs succeeded for the individual files, but the top-level directory-manifest object apparently never fully round-tripped to the remote in a retrievable way, even though dvc's local state believed it had. This looked like a genuine remote-sync inconsistency rather than a mistake in our commands, and is worth flagging to an instructor if a working `dvc pull` on a fresh clone is graded.

**In simple terms:**
**`git clone` → code + `data.dvc` pointer only**
**`dvc pull` → meant to fetch the actual data using that pointer (worked for us in principle, but exposed a real remote-sync gap in practice)**

---

## Question 8 — Do you still see `food11_processed` and `food11_processed_mini`?

No.

After running:

```
git checkout 86d8ea7
dvc checkout
```

the `data/` folder contained only:

```
food11_raw
```

The folders `food11_processed` and `food11_processed_mini` were gone.

**A wrinkle we hit here too:** the first `dvc checkout` failed with a config error, because `.dvc/config` itself was empty at that older commit (it predated the commit where the DagsHub remote URL was configured). Fixed by pulling the current config back in without leaving the old commit:

```
git checkout main -- .dvc/config
dvc checkout
```

After that, `data/` correctly showed only `food11_raw`.

**Why?**

The commit `86d8ea7` was created *before* the processed datasets existed. `git checkout 86d8ea7` restores the old `data.dvc` pointer (and every other tracked file, including `.dvc/config`, to that point in time). `dvc checkout` then makes the actual `data/` folder match that older pointer — so anything added after that commit simply isn't part of it.

**What this demonstrates:**

* **`git checkout`** → restores old code and the old `data.dvc` pointer (and can restore *other* config files along with it, which caught us off guard).
* **`dvc checkout`** → restores the matching old data to disk.

To return to the newest version:

```
git checkout main
dvc checkout
```

This brings the project back to the latest code and data.
