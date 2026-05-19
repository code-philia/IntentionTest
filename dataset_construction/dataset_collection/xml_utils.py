# read pom.xml using BeautifulSoup

from bs4 import BeautifulSoup
import bs4
import re
import subprocess
import os

orig_prettify = bs4.BeautifulSoup.prettify
r = re.compile(r'^(\s*)', re.MULTILINE)
def prettify(self, encoding=None, formatter="minimal", indent_width=4):
    return r.sub(r'\1' * indent_width, orig_prettify(self, encoding, formatter))
bs4.BeautifulSoup.prettify = prettify

def read_pom_xml(pom_xml_path):
    with open(pom_xml_path, 'r') as f:
        content = f.read()
    soup = BeautifulSoup(content, 'xml')
    return soup

'''
Insert the following:
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>0.7.7.201606060606</version>
    <executions>
        <execution>
            <goals>
                <goal>prepare-agent</goal>
            </goals>
        </execution>
        <execution>
            <id>report</id>
            <phase>prepare-package</phase>
            <goals>
                <goal>report</goal>
            </goals>
        </execution>
    </executions>
</plugin>

into project -> build -> plugins
'''
def insert_jacoco(file_path):
    soup = read_pom_xml(file_path)
    plugin = construct_jacoco_plugin(soup)
    if soup.find("project") is None:
        return
    
    # make a backup first
    args = ["cp", file_path, file_path + ".bak"]
    subprocess.run(args)

    if soup.find("project").find("build") is None:
        soup.find("project").append(soup.new_tag("build"))
    if soup.find("project").find("build").find("plugins") is None:
        soup.find("project").find("build").append(soup.new_tag("plugins"))
    
    # check whether the plugin is already there. if it is, delete it
    plugins = soup.find('project').find('build').find('plugins').findAll('plugin')

    while True:
        found = False
        for p in plugins:
            # print(p.find('artifactId').string)
            if p.find('artifactId') is not None and p.find('artifactId').string is not None and p.find('artifactId').string.strip() == 'jacoco-maven-plugin':
                p.decompose()
                found = True
                break
        if not found:
            break

    soup.find('project').find('build').find('plugins').append(plugin)
    
    # save with 4 spaces indentation
    with open(file_path, 'w') as f:
        f.write(soup.prettify())

def construct_jacoco_plugin(soup):
    plugin = soup.new_tag('plugin')
    group_id = soup.new_tag('groupId')
    group_id.string = 'org.jacoco'
    plugin.append(group_id)
    artifact_id = soup.new_tag('artifactId')
    artifact_id.string = 'jacoco-maven-plugin'
    plugin.append(artifact_id)
    version = soup.new_tag('version')
    version.string = '0.7.7.201606060606'
    plugin.append(version)
    executions = soup.new_tag('executions')
    execution1 = soup.new_tag('execution')
    goals1 = soup.new_tag('goals')
    goal1 = soup.new_tag('goal')
    goal1.string = 'prepare-agent'
    goals1.append(goal1)
    execution1.append(goals1)
    executions.append(execution1)
    execution2 = soup.new_tag('execution')
    id2 = soup.new_tag('id')
    id2.string = 'report'
    phase = soup.new_tag('phase')
    phase.string = 'prepare-package'
    goals2 = soup.new_tag('goals')
    goal2 = soup.new_tag('goal')
    goal2.string = 'report'
    goals2.append(goal2)
    execution2.append(id2)
    execution2.append(phase)
    execution2.append(goals2)
    executions.append(execution2)
    plugin.append(executions)

    return plugin

# insert_jacoco('pom.xml')

# for all pom.xmls inside /bernard/dataset_construction/prep/repos, run insert_jacoco(file_path)
for root, dirs, files in os.walk('/bernard/dataset_construction/prep/up_to_date_repos'):
    for file in files:
        if file == 'pom.xml':
            insert_jacoco(os.path.join(root, file))