# Lab 4 - Orchestrating the app with Docker Compose

## Question 1: What happens to everything written to /mlflow-data if you never mount a volume there and just docker run this image standalone? Try it: run the container, register nothing, stop it, remove it, start a new one from the same image — what do you see in the UI?

Didn't need to run this as a separate test, I basically watched it happen for real. Without a volume, everything mlflow writes to /mlflow-data, the sqlite db, the artifacts, just lives in the container's own writable layer. Kill the container and start a fresh one from the same image and the UI comes up completely empty, new mlflow.db, nothing registered. The image only has the server code baked in, not anything it creates while running.

## Question 2: Why a named volume here instead of a bind mount to a folder in your repo (the way you might for local dev)? Would a bind mount work just as well?

A named volume isn't tied to any path in my repo, Docker just manages it. Mine actually got tested harder than planned, my laptop powered off mid-session and when it came back on, everything I'd registered was still there untouched. A bind mount to a repo folder would also survive restarts, but then the container depends on my exact folder layout, and I'd end up with runtime junk, sqlite db, artifact blobs, sitting inside my repo where it doesn't belong.

## Question 3: In Lab 3 you had to use host.docker.internal or --network host to reach mlflow from inside the container. In this lab, MLFLOW_TRACKING_URI will simply be http://mlflow:5000. Why does that hostname resolve now when it didn't before?

In Lab 3 I needed host.docker.internal because the container wasn't on any network with mlflow, it just had to reach out to my host. Here, mlflow and inference are both services on the same Compose network, and Compose runs its own DNS that maps each service name to its container. mlflow isn't magic, it's literally the name I gave the service in docker-compose.yml.

## Question 4: Why does the frontend read INFERENCE_URL from an environment variable instead of hardcoding http://inference:8000? Think about what happens if you ever docker run this frontend image on its own, outside Compose.


If I hardcoded the inference address in app.py, the frontend image would only ever work inside this exact Compose stack. Reading it from an env var instead means I could still run the same frontend image on its own against some other inference service, no rebuild, just a different value passed in.

## Question 5: Only mlflow and frontend publish a port to the host. inference doesn't. Why not, and how does the frontend still reach it?

Only mlflow and frontend publish a port, 5000 and 8501, because those are the two I actually need to open in a browser. inference has no ports line at all, frontend just calls it directly over the internal network, same DNS thing as Q3. docker compose ps backs this up, inference only shows 8000/tcp with no host mapping, the other two show the host port mapped.

## Question 6: depends_on here only waits for the mlflow container process to start, not for the tracking server inside it to be ready to accept connections. If your serve.py tries to load the Staging model at startup and mlflow isn't ready yet, what happens to the inference container? Look at docker compose logs inference if it fails.

Hit this exactly as described. inference's container started right after mlflow's did, but mlflow wasn't actually accepting connections yet, so inference just sat on waiting for application startup with nothing else showing up in the logs. It was stuck trying to load the model from a server that wasn't up yet. Fixed itself once mlflow was confirmed fully up and I restarted inference.

## Question 7: Run docker compose ps. Which services have a published port listed, and which don't? Does that match what you'd expect from the docker-compose.yml?

frontend and mlflow show a published port in the output, inference doesn't. Matches exactly what I'd expect from Q5, since only those two have a ports entry in the compose file.

## Question 8: Refresh the frontend and upload an image again. Does the prediction come from the new model version, or the old one? Your serve.py loads the model once, at startup — what single command lets you pick up the new Staging version without rebuilding any image?

Registered a new model version and moved the champion alias onto it, then just restarted the inference container. No rebuild. Checked the running container against the registry right after and it was serving the new version, next prediction used the new model.

## Question 9: Why does restart alone work here — no rebuild needed? What does that tell you about what's baked into the inference image versus fetched at container startup?

The inference image only has code and dependencies baked in, not the model itself. serve.py loads the model by alias when the process starts, so restarting the container just reruns that startup logic against whatever mlflow says is champion right now. There's nothing model-specific in the image to rebuild.

## Question 10: Is your registered model and its Staging assignment still there after this down/up cycle? Now try docker compose down -v followed by docker compose up — what's different this time, and why?

Took the stack down and back up normally, everything was still there, checked the mlflow data directory and both model versions' artifact folders were exactly where I left them. Down tears down containers and the network but leaves the volume alone.

Took it down with the -v flag and back up, the volume itself got wiped and recreated empty, nothing left in it at all, no db, no mlruns folder. The -v flag is the one that actually deletes the volume, a plain down never touches it.

## Question 11: This compose file is still meant to run on one machine. What would have to change for the inference service to run as three replicas behind a load balancer, or for the mlflow service to survive a machine failure? (You don't need to implement this — just name what Docker Compose can't give you here.)

This is all still one machine. To run inference as several replicas behind a load balancer I'd need something that actually schedules containers across multiple hosts and balances traffic between them, Compose's own scale option just spins up more containers on the same box, no cross-host scheduling, no real load balancer. That's what Kubernetes or Swarm are for. For mlflow to survive a machine dying, the backend store, sqlite on a local volume right now, would have to become a real replicated database, and the artifacts would have to move off the local volume to something like S3, since a named volume lives on one host's disk, and if that host is gone, so is everything in it.