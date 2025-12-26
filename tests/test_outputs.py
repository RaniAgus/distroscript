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

SCRIPT_GENERATOR = 'installscript.py'
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
                print(f"SKIP: No expected file for {input_file} on {os_type}")
                continue
            expected_file = expected_files[0]  # Assume only one

            # Run the generator
            result = subprocess.run(
                ['python3', SCRIPT_GENERATOR, input_file, '--os', os_type],
                capture_output=True, text=True, check=True
            )
            generated_script = result.stdout

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
            except subprocess.CalledProcessError:
                # If git diff fails, try regular diff (no colors)
                diff_result = subprocess.run(
                    ['diff', expected_file, temp_path],
                    capture_output=True, text=True
                )
                if diff_result.returncode == 0:
                    pass_count += 1
                    print(f"{GREEN}[PASS] {base} for {os_type}{RESET}")
                else:
                    fail_count += 1
                    print(f"{RED}[FAIL] {base} for {os_type}{RESET}")
                    print(diff_result.stdout)
            finally:
                os.unlink(temp_path)

    print(f"\n{BOLD}Results:{RESET} {GREEN}{pass_count} passed{RESET}, {RED}{fail_count} failed{RESET}")

if __name__ == '__main__':
    main()
