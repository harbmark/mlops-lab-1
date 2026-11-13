import argparse
import math
import os
import sys

from mlflow.exceptions import MlflowException

import mlflow

MODEL_NAME = "food11"
METRIC = "test_accuracy"
Z = 2  # candidate must beat the champion by Z standard errors


def accuracy_of(client, version):
    if not version.run_id:
        sys.exit(f"version {version.version} has no source run, cannot read {METRIC}")
    value = client.get_run(version.run_id).data.metrics.get(METRIC)
    if value is None:
        sys.exit(f"run {version.run_id} (version {version.version}) has no metric {METRIC}")
    return value


def main():
    parser = argparse.ArgumentParser(description="Quality gate for promoting a model version.")
    parser.add_argument("--version", type=int, required=True, help="candidate version number")
    parser.add_argument("--n-test", type=int, default=363, help="size of the test split")
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"))
    client = mlflow.MlflowClient()

    candidate = client.get_model_version(MODEL_NAME, str(args.version))
    acc_candidate = accuracy_of(client, candidate)

    try:
        champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except MlflowException:
        champion = None

    if champion is None:
        print("no champion yet, promoting the candidate directly")
        client.set_registered_model_alias(MODEL_NAME, "champion", str(args.version))
        client.set_model_version_tag(MODEL_NAME, str(args.version), "gate_decision", "promoted (no champion)")
        client.set_model_version_tag(MODEL_NAME, str(args.version), "gate_candidate_accuracy", f"{acc_candidate:.4f}")
        return

    if int(champion.version) == args.version:
        sys.exit(f"version {args.version} is already the champion")

    acc_champion = accuracy_of(client, champion)
    se = math.sqrt(acc_champion * (1 - acc_champion) / args.n_test)
    threshold = acc_champion + Z * se
    promote = acc_candidate >= threshold

    decision = "promoted" if promote else "rejected"
    print(f"champion  v{champion.version}: test_accuracy={acc_champion:.4f}")
    print(f"candidate v{args.version}: test_accuracy={acc_candidate:.4f}")
    print(f"standard error={se:.4f}  required >= {threshold:.4f}  (2*se = {Z * se * 100:.1f} points)")
    print(f"decision: {decision}")

    if promote:
        client.set_registered_model_alias(MODEL_NAME, "champion", str(args.version))
    else:
        client.set_registered_model_alias(MODEL_NAME, "challenger", str(args.version))

    tags = {
        "gate_decision": decision,
        "gate_candidate_accuracy": f"{acc_candidate:.4f}",
        "gate_champion_accuracy": f"{acc_champion:.4f}",
        "gate_champion_version": str(champion.version),
        "gate_threshold": f"{threshold:.4f}",
    }
    for key, value in tags.items():
        client.set_model_version_tag(MODEL_NAME, str(args.version), key, value)


if __name__ == "__main__":
    main()