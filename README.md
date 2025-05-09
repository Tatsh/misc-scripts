# Miscellaneous scripts

[![QA](https://github.com/Tatsh/misc-scripts/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/misc-scripts/actions/workflows/qa.yml)

Random scripts I make and might still use.

## Deprecation notice

This repository is deprecated. Visit [deltona](https://github.com/Tatsh/deltona) to see the
successor project.

## Poetry usage

```shell
git clone git@github.com:Tatsh/misc-scripts.git
cd misc-scripts
poetry install
poetry shell
```

Now all Python scripts will work.

## ucwords

Performs title casing on strings. Accepts standard input. Typical use:

```shell
echo "my lowercase string needs some fixes" | ucwords
```
