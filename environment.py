""" This loads environment variables from a defined location """
import os
import pathlib

import os
import pathlib


def load_env(locations=['.env', '../.env', '../env/.env', '../../../.env']):
    env_file = None
    for loc in locations:
        path = pathlib.Path(loc)
        if path.exists() and path.is_file():
            env_file = loc
            break

    if env_file is not None:
        with open(env_file) as f:

            # Read all lines in the file and determine if they contain 'export' and are not comments
            all_lines = [
                line.strip().split('=', 1)
                for line in f
                if not line.startswith('#') and line.strip()
            ]

            # Filter out 'export' if present and only keep lines with exactly two parts
            processed_lines = [
                (line[0].replace('export ', ''), line[1])
                if 'export ' in line[0]
                else line
                for line in all_lines
                if len(line) == 2
            ]

            # Update the environment variables
            os.environ.update(dict(processed_lines))

            #### Print the keys of the environment variables added/updated, one per line
            # print("Loaded environment variable keys")
            # for key, _ in processed_lines:
            #     print(f"  {key}:{_}")


if __name__ == "__main__":
    load_env()
