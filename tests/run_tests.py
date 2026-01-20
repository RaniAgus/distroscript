#!/usr/bin/env python3
"""
Test script to run each input YAML for Fedora and Ubuntu,
generate the install script, and compare to expected output.
If different, show git diff.
"""

import os
import glob
import subprocess
import tempfile

SCRIPT_GENERATOR = 'src/installscript.py'
OS_TYPES = ['fedora', 'ubuntu']

# ANSI color codes
BOLD = '\033[1m'
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

def main():
    inputs_dir = 'tests/inputs'
    outputs_dir = 'tests/outputs'

    # Change to the project root
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    pass_count = 0
    fail_count = 0

    for input_file in sorted(glob.glob(os.path.join(inputs_dir, '*.yml'))):
        base = os.path.basename(input_file)
        number = base.split('-')[0]

        for os_type in OS_TYPES:
            expected_pattern = os.path.join(outputs_dir, os_type, f"{number}-*.sh")
            expected_files = glob.glob(expected_pattern)
            if not expected_files:
                print(f"[SKIP] No expected file for {input_file} on {os_type}")
                continue
            expected_file = expected_files[0]  # Assume only one

            try:
                # Run the generator
                result = subprocess.run(
                    ['python3', SCRIPT_GENERATOR, input_file, '--os', os_type],
                    capture_output=True, text=True, check=True
                )
                generated_script = result.stdout[:-1] if result.stdout.endswith('\n') else result.stdout
            except subprocess.CalledProcessError as e:
                fail_count += 1
                print(f"{RED}[ERROR] {base} for {os_type} - generator failed{RESET}")
                print(f"Command: {' '.join(e.cmd)}")
                print(f"Return code: {e.returncode}")
                print(f"Stdout: {e.stdout}")
                print(f"Stderr: {e.stderr}")
                continue  # Skip the diff part

            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as temp:
                temp.write(generated_script)
                temp_path = temp.name

            try:
                # Run git diff with colors
                diff_result = subprocess.run(
                    ['git', 'diff', '--no-index', '--color=always', expected_file, temp_path],
                    capture_output=True, text=True
                )
                if diff_result.returncode == 0:
                    pass_count += 1
                    print(f"{GREEN}[PASS] {base} for {os_type}{RESET}")
                else:
                    fail_count += 1
                    print(f"{RED}[FAIL] {base} for {os_type}{RESET}")
                    print(diff_result.stdout)
            except subprocess.CalledProcessError as e:
                # If git diff fails, show the error
                fail_count += 1
                print(f"{RED}[ERROR] {base} for {os_type} - git diff failed{RESET}")
                print(f"Error: {e}")
                print(f"Stdout: {e.stdout}")
                print(f"Stderr: {e.stderr}")
            except Exception as e:
                # Other exceptions
                fail_count += 1
                print(f"{RED}[ERROR] {base} for {os_type} - unexpected error{RESET}")
                print(f"Error: {e}")
            finally:
                os.unlink(temp_path)

    print(f"\n{BOLD}Results:{RESET} {GREEN}{pass_count} passed{RESET}, {RED}{fail_count} failed{RESET}")

    if fail_count > 0:
        exit(1)

if __name__ == '__main__':
    main()
