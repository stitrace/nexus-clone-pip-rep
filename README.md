### How to use:
Create and clone repo in Nexus:
```
python3 copy-pip-repo.py -m create -s production -d production-hotfix-1234 --fqdn nexus.company.com
```
Remove repository:
```
python3 copy-pip-repo.py -m delete -d production-hotfix-1234 --fqdn nexus.company.com
```