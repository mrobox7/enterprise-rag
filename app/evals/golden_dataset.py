from typing import TypedDict


class GoldenExample(TypedDict):
    question: str
    ground_truth: str


GOLDEN_DATASET: list[GoldenExample] = [
    # --- Databricks CLI ---
    {
        "question": "What are the three ways to run a job using the Databricks CLI?",
        "ground_truth": (
            "Scheduled (if the job definition includes a schedule, it runs automatically), "
            "triggering with `databricks jobs run-now` for a job that already exists, and "
            "triggering with `databricks jobs submit`, which takes a job definition and runs "
            "it once without saving it."
        ),
    },
    # --- fine parallel processing / work queue ---
    {
        "question": "In the job-wq-2 Job manifest, what field controls how many pods run concurrently, and what is it set to?",
        "ground_truth": "spec.parallelism, set to 2.",
    },
    # --- Kubernetes Jobs core ---
    {
        "question": "What are the three restart policy options for a Job's pod template, and which one is disallowed?",
        "ground_truth": (
            "OnFailure (kubelet restarts the container in place), Never (the whole Pod is "
            "marked failed and the Job controller creates a new one), and Always, which is "
            "not allowed because it would prevent the Pod from ever completing."
        ),
    },
    {
        "question": "What is the difference between NonIndexed and Indexed completion modes for a Job?",
        "ground_truth": (
            "In NonIndexed mode (the default) all Pods are identical. In Indexed mode, each "
            "Pod gets a unique completion index, exposed as $JOB_COMPLETION_INDEX, allowing "
            "each Pod to process a distinct slice of data."
        ),
    },
    {
        "question": "Which kubectl command shows the completions, duration, and age of jobs in a cluster?",
        "ground_truth": "`kubectl get jobs`, which lists NAME, COMPLETIONS, DURATION, and AGE for each job.",
    },
    # --- pods_autoscale.html ---
    {
        "question": "In the HPA practical example, what metric and target utilization does the nginx-hpa autoscaler use, and what are its min/max replicas?",
        "ground_truth": "It targets CPU resource utilization with an averageUtilization target of 50%, with minReplicas 1 and maxReplicas 10.",
    },
]
