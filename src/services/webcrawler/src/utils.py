# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import os
import shutil
from urllib.parse import urlparse


async def check_and_create_directory(save_path: str):
    """
        Checks and creates the parent directory of the specified file.
        If the target file already exists, returns status code 400 with an error message.

        :param save_path: The full path of the target file
        :return: Returns {"status": 400, "message": "File already exists"} if the file exists; otherwise, returns nothing
    """
    save_path = Path(save_path)
    save_dir = save_path.parent  # Get the parent directory of the file
    # Create the directory if it does not exist
    if not save_dir.exists():
        try:
            save_dir.mkdir(parents=True, exist_ok=True)  # Recursively create directories
        except Exception as e:
            print(f"Failed to create directory {save_dir}. Exception: {e}")
            raise Exception(f"Failed to create directory {save_dir}. Exception: {e}")
    # If the target file already exists, return an error message
    if save_path.exists():
        return {"status": 400, "message": f"File {save_path} already exists."}


async def delete_directory(dir_path):
    """
    Delete all files and subdirectories within the specified directory while preserving the directory itself.
    :param dir_path: Path of the directory to be cleaned
    """
    if os.path.isdir(dir_path):
        try:
            for entry in os.listdir(dir_path):
                entry_path = os.path.join(dir_path, entry)
                if os.path.islink(entry_path):
                    os.unlink(entry_path)
                elif os.path.isfile(entry_path):
                    os.unlink(entry_path)
                else:
                    shutil.rmtree(entry_path)
            print(f"All contents in directory '{dir_path}' have been successfully deleted.")
        except Exception as e:
            print(f"Error occurred during deletion: {str(e)}")
    else:
        print(f"Directory '{dir_path}' does not exist.")
# example
# target_directory = "/path/to/your/directory"
# delete_directory(target_directory)

def is_url(s):
    """
    Check if a string is a valid URL.
    """
    try:
        result = urlparse(s)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False