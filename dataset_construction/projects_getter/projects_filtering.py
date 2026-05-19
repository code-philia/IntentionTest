import numpy as np
import pandas as pd
import os
import subprocess

ROOT_PATH = '/bernard/dataset_construction/prep'

df = pd.read_csv('urls_new.csv', header=None)

start_i = 0
end_i = len(df)

# Get subset of df
df = list(df.iloc[start_i:end_i][0])

# Make repos directory
os.chdir(os.path.normpath(ROOT_PATH))
if not os.path.exists('repos'):
    os.mkdir('repos')

def git_clone(url):
    os.chdir(os.path.normpath(ROOT_PATH+'/repos'))
    # check whether exists
    if os.path.exists(url.split('/')[-1]):
        return
    subprocess.run(['git', 'clone', '--depth=1', url])

def remove_folder(url):
    os.chdir(os.path.normpath(ROOT_PATH+'/repos'))
    subprocess.run(['rm', '-rf', url.split('/')[-1]])

def check_pom_xml(url):
    os.chdir(os.path.normpath(ROOT_PATH+'/repos/'+url.split('/')[-1]))
    return os.path.exists('pom.xml')

def compile(url):
    os.chdir(os.path.normpath(ROOT_PATH+'/repos/'+url.split('/')[-1]))

    result = subprocess.run(['mvn', 'clean', 'compile'], timeout=60, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return result


new_ls = []

# for loop with logging
for i, url in enumerate(df):
    print(f"Processing {i + 1}/{len(df)}: {url}")
    try:
        git_clone(url)
        has_pom = check_pom_xml(url)

        if not has_pom:
            print(f'No pom.xml for {url}')
            remove_folder(url)
            continue

        # Try to compile
        print(f"Compiling {url}")
        result = compile(url)

        if result.returncode == 0:
            print(f'Successfully compiled {url}')
            new_ls.append(url)
        else:
            print(f'Error compiling for {url}')
            remove_folder(url)
    except subprocess.TimeoutExpired:
        print(f'Timeout for {url}')
        remove_folder(url)
    except Exception as e:
        print(f'Error for {url}: {e}')
        remove_folder(url)

# Save the new list locally
new_df = pd.DataFrame(new_ls)
os.chdir(os.path.normpath(ROOT_PATH))
new_df.to_csv('urls_filtered.csv', index=False, header=False)