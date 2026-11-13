# Lab 5 – CI/CD with GitHub Actions

## What I did

Made the code testable, wrote unit tests and a data contract check, set up a GitHub Actions workflow that lints, tests, builds the Docker image, checks that the container starts and pushes the image to ghcr.io, protected main with a ruleset, and wrote a promotion script that applies a quality gate before the champion alias moves.

## Q1 – Why not load the real model in a unit test

The test would depend on things it doesn't control, so it could fail even when my code is correct. The MLflow server might not be running or reachable, and on the GitHub runner there is no server at all since mine lives on my laptop. The champion alias might have moved, so the model that loads isn't the one I expected. The artifacts might be stored as a path that only exists on my machine, which is exactly what bit me in Lab 3 and Lab 4. The model might have been saved on a GPU and fail on a CPU only machine. It would also be slow, the model file is about 45 MB, and a red test wouldn't tell me whether my code or the model is the problem.

## Q2 – What the fake model test proves

It proves my code around the model works: the endpoint accepts an uploaded jpg, decodes it, runs the preprocessing, calls predict, turns the output into a category and a confidence, and returns valid JSON with a 200 status and a confidence between 0 and 1. It proves nothing about the model itself. It doesn't show the real model loads, that it is accurate, or that the class order is right, and since the fake always answers Bread it would pass for any image. It doesn't even check the confidence value: the fake returns 0.90, but serve.py runs a softmax on whatever the model returns, so the confidence I actually get back is about 0.2, and the test still passes because it only checks the 0 to 1 range.

## Q3 – Which check caught the duplicate

Check 4, no image appears in two splits. I copied one training image into evaluation and it printed the training file next to the copy. A duplicate is more dangerous than a corrupted image because a corrupted image is loud, the training script crashes and I fix it. A duplicate is silent: the model has already seen that test image, so the test accuracy comes out higher than it really is, nothing fails, and I would trust a number that is wrong. The same check also found 4 real duplicate pairs between validation and evaluation (Dessert and Seafood) in my mini dataset before I broke anything.

## Q4 – Where validate_data.py should run

The first place is on my laptop right after the processed data is produced and before it is pushed with dvc, for example as a step in the data preparation or a pre-push hook, so bad data never reaches the remote. The second place is at the start of the training run, before train.py begins, on whatever machine actually has the data. If I want it in CI too, I could run it on a small sample dataset committed in git like the bread fixture, or do a dvc pull with credentials stored as secrets.

## Q5 – needs: test on the smoke job

If a unit test fails, the smoke job doesn't run, it shows as skipped. I saw this on my pull request, test failed and both smoke and push were skipped. Without needs, the jobs would start at the same time, so the docker build and container check would run even though the tests failed, wasting minutes, and smoke could show green next to a red test.

## Q6 – Run time and the second run

The first run took 2m 0s (test 22s, smoke 1m 32s) and the second run, the empty commit, took 2m 5s (test 24s, smoke 1m 36s). Nothing got faster. The uv cache was restored in the second run, but it was only 3730 bytes, because setup-uv prunes the pre-built wheels before saving the cache, so uv sync downloaded everything again. The docker build has no layer cache either since every job starts on a fresh machine, and that is most of the time.

## Q7 – SHA instead of latest

The commit SHA points to exactly one version of the code and never changes, so I can tell which commit a running container was built from and go back to an older one. latest is just a label that moves. A concrete case: I deploy on Monday and my machine pulls latest, a teammate pushes on Tuesday, and on Wednesday a second machine pulls latest. Both run something called latest but with different code, and a machine that already has the image locally won't even pull the new one. This also answers question 9 of Lab 3.

## Q8 – Why the push job declares permissions

It gives the job only what it needs, contents read and packages write, instead of whatever the default token permissions are. If one of the steps gets compromised, for example a third party action or a dependency that turns malicious, it can only do what the token allows. With write access to everything in the repo it could push commits to main, change the workflow files, delete releases or branches, or push a poisoned image. With the limited token the damage stays inside the packages.

## Q9 – The pull request page

It showed some checks were not successful, 2 failing and 4 skipped. The test check failed, smoke and push were skipped, and the Merge pull request button was greyed out. There was also a red checkbox to merge without waiting for the requirements, but it only appears because I am a repo admin on the bypass list, a teammate wouldn't have it. For a team it changes the rule from everybody should run the tests before pushing to GitHub refusing the merge unless the checks pass. Nobody can forget or skip it, the failure is visible to everyone reviewing, and the tests run on a clean machine instead of someone's laptop where things might work by accident. The checks ran twice, once for the push to the branch and once for the pull request, because the workflow listens to both events.

## Q10 – What the gate decided

The champion is version 1 with a test accuracy of 0.6226. My test set has 363 images, so the standard error is 0.0254 and 2 times that is 5.1 accuracy points, which means a candidate needs at least 0.6735.

The first candidate, version 2, used a very small learning rate (0.000001) and got 0.1074, so it was rejected and got the challenger alias. The second candidate, version 3, used my best settings (lr 0.0001, 5 epochs) and got 0.6391, which is 1.65 points better than the champion but under the 5.1 point margin, so it was also rejected and took the challenger alias from version 2. The champion stayed on version 1 and the decision and the numbers are saved as tags on both versions.

## Q11 – Running promote.py automatically

One way is to use a hosted MLflow server, like the one DagsHub gives for the repo, so the cloud runner can reach it, and run promote.py as a GitHub Actions job after training, with the tracking URI and token stored as secrets. The other is to keep MLflow on my machine and run promote.py there, either as the last step of the training script or pipeline right after train.py, or through a self hosted GitHub runner installed on my laptop that can reach localhost:5000.

## Q12 – The pipeline from git push to a running container

```
CODE LANE

  write code, run ruff and pytest locally ............ human
        |
  git push to a branch, open a pull request .......... human
        |
  CI: test (ruff + pytest) ........................... automatic
        |
  CI: smoke (docker build, start with SKIP_MODEL,
             curl /health) ........................... automatic
        |
  ruleset: merge allowed only if test and smoke
           are green ................................. automatic
        |
  review and click Merge into main ................... human
        |
  CI on main: push job builds the image and pushes
  ghcr.io/harbmark/mlops-lab-1:<commit sha> .......... automatic
        |
        |   CODE VERSION is decided here: the commit
        |   SHA used as the image tag
        |
  docker pull the image and start the container ...... human


MODEL LANE (separate, not triggered by the pipeline)

  train.py logs a run to MLflow ...................... human
        |
  register the run as a new model version ............ human
        |
  promote.py compares test accuracy with the
  champion and moves the alias or sets challenger .... human starts it,
        |                                              the decision is automatic
        |   MODEL VERSION is decided here: the
        |   champion alias in the registry
        |
  restart the inference container so it loads
  models:/food11@champion at startup ................. human


The two lanes only meet when the container starts: the image (code version)
loads whichever model the champion alias points to (model version).
```
