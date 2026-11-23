import os

# Tests never touch GitHub: read repo files from the working copy.
os.environ["DATA_SOURCE"] = "local"
