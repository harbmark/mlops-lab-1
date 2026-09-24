# Lab3 - Docker

## Question 1: Open the "Models" tab in the mlflow UI. What version number was your model given? What's the difference between a run's logged model artifact and a registered model?

I had multiple runs logged under the food11 experiment. I sorted the runs
table by val_accuracy descending in the MLflow UI to find the actual best
one. At first I almost registered marvelous-rook-476 just because it was
the most recent run, but once I sorted properly caring-ant-3 was clearly
the best with val_accuracy = 0.5868 (vs 0.4353 for the other one), so I
registered that one instead.
This created a registered model called food11, Version 1. I checked the
UI afterward and It correctly shows caring-ant-3, so I know I
registered the right run.

## Question 2: What aliases replaced the old built-in stages in mlflow? Why version a model separately from the run that produced it, and why is an alias more flexible than a fixed stage name?

I checked in the UI and Version 1 now shows @champion next to it.
Aliases are the newer way of doing what used to be Staging/Production
stages, they're just a name that points at whichever version I want, and I
can move it later without changing any serving code.

## Question 3: Why load the model through an mlflow model URI (models:/food11@champion) instead of pointing directly at the .pth file on disk? What would you have to change to serve a newer model version?

In serve.py I load the model like this using this command:
model = mlflow.pyfunc.load_model("models:/food11@champion")
instead of pointing at a specific .pth file somewhere. The point is that
if I retrain later and register a new champion, I just move the alias, 
serve.py doesn't need to change at all, since it always asks for
"whatever champion currently is.
To actually check this was working and not just silently returning
garbage, I added a temporary debug print of the raw model output and
confirmed the shape was (1, 11), one prediction across the 11 food
categories, which is what I'd expect. I removed the debug line after. Then
I tested /predict against a few real validation images and the
predictions were mixed but reasonable, right on some (Bread, Seafood),
wrong but understandable on others, which actually lines up with my
model's real accuracy (around 58 to 62%), so I'm confident it's genuinely
running inference and not coincidentally not crashing.

## Question 4: Why copy pyproject.toml/uv.lock and run uv sync before copying the rest of the source code, instead of copying everything at once? What happens to the build cache when you only change a line in serve.py?

In the Dockerfile I copy pyproject.toml, uv.lock, and README.md
before I copy src/, and I run the dependency install on that layer by
itself. Docker only re-runs a layer if its inputs changed, so this way,
editing serve.py doesn't force the whole dependency install to happen
again, only copying the manifest files does.
I actually needed two separate uv sync calls, not one, because of a real
error I hit. My first attempt ran uv sync --frozen --no-dev right after
copying the manifests, before src/ existed yet, and it failed.
Turns out uv sync without --no-install-project also tries to build my
own local package, which needs src/ to exist. So I split it: first
uv sync --frozen --no-dev --no-install-project (just the dependencies,
before src/ is copied), then COPY src/ ./src/, then a second
uv sync --frozen --no-dev to actually install my package. That second
call only took 0.4 seconds in my build log, while the dependency layer took
somewhere around 15-18 minutes, so keeping them separate is exactly what
makes rebuilds fast when I only change my code.
I also had to add README.md to that first COPY line, because
pyproject.toml points to it as the project's readme, and without it in
the build context uv sync failed with No such file or directory.

## Question 5: What's the size difference between a naive single-stage image and your multi-stage one? Use docker history <image> to see which layers are the biggest.

Docker history shows about 1.59 GB total, almost all of it 1.45 GB is the venv (torch, mlflow, sklearn, etc). Started out much worse, a leftover CUDA config from Lab 2 in pyproject.toml was pulling in almost 18 nvidia packages and made the dependency install take 39+ minutes. Removed it, reran uv lock, install time dropped to 15-18 mins.

## Question 6: What happens to build speed and image size if you forget the .dockerignore? Which of the excluded folders would actually break the build if they were sent to the Docker daemon?

Without this .dockerignore , Docker would try to send my local '.venv/', the whole Food-11
dataset in 'data/', my local MLflow tracking files, and '.git/' into the
build , none of which the container needs, and some of which is genuinely
large. I actually confirmed this worked: in my build logs, the
"transferring context" step was always under 1 MB (like 917 kB), so I know
the dataset and local venv never actually got sent to Docker.

## Question 7: Why can't the container simply use 127.0.0.1:5000 to reach the mlflow server on your host? What does host.docker.internal resolve to?

serve.py reads MLFLOW_TRACKING_URI from an env var, defaulting to 127.0.0.1:5000. Inside the container that points at itself, not my host, so I ran it with -e MLFLOW_TRACKING_URI=http://host.docker.internal:5000.
Hit three separate issues getting this to actually work:
MLflow rejected the request with a "DNS rebinding" 403, fixed by restarting the server with MLFLOW_SERVER_ALLOWED_HOSTS set to include host.docker.internal:5000.
The model's artifacts were stored as a local path on my machine, which the container can't see, fixed with a --mount bind mount of my mlruns folder into the container.
The model was originally saved from a CUDA run, so torch.load tried to load it onto a GPU that doesn't exist in the container, fixed by patching torch.load in serve.py to force map_location="cpu".
Once all three were fixed, /predict on a test image worked and matched my local non-Docker test almost exactly.

## Question 8: Stop the container and start a new one from the same image. Does the model still load correctly without you rebuilding? What does that tell you about what's baked into the image versus fetched at runtime?

I stopped the running container and started it again with the exact same
docker run command, without running docker build again. /health
came back with status: ok right away. That confirmed the image itself
doesn't need to be rebuilt just to restart the service, the container
just recreates itself from the same image each time.


## Question 9: The Dockerfile and image are versioned differently — one lives in git, the other doesn't (yet). What's still missing before another machine (like a CI runner or a Kubernetes cluster) could reliably pull and run the exact image you just built?

Two things I actually ran into, not just theory:

1. I only ever tagged my image as 'latest', so every rebuild silently
   overwrote the previous one. There's no way to tell which image build
   matches which git commit, or roll back. In a real pipeline I'd tag by
   git commit hash or a version number and push it to a registry.
2. My model's artifacts live on my own laptop's filesystem, and the only
   reason the container could reach them is that I manually bind-mounted
   that exact folder in. That obviously wouldn't work on a CI runner or in
   Kubernetes, there's no "my laptop" to mount there. The real fix would
   be storing artifacts somewhere remote like S3 or running MLflow with
   --serve-artifacts from the very start, so models get fetched over HTTP
   instead of needing direct access to my disk.
