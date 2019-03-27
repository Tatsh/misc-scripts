# Miscellaneous scripts

Random scripts I make and might still use.

## Using virtualenv

I recommend using [virtualenvwrapper](http://virtualenvwrapper.readthedocs.org/en/latest/). You can still use virtualenv though:

```bash
virtualenv misc-scripts-env
cd misc-scripts-env
. bin/activate
git clone git@github.com:Tatsh/misc-scripts.git
pip install -r misc-scripts/requirements.txt
```

Now all scripts using Python should work. See `requirements.txt` for details on command line applications required.

## chrome-import-cookies

Imports cookies from a file in Netscape 'cookies.txt' format into Chromium's (Chrome) 'Default' user database. For Linux only at the moment.

Usage: `chrome-import-cookies COOKIES_TXT_FILE`

## mozcookie2chrome

Given a domain, inserts/replaces cookies in Chromium's database with ones from Firefox. The argument is placed in a `LIKE` statement wrapped in `%` so anything is usable.

Usage: `mozcookie2chrome DOMAIN`

## smv

Like `scp` but deletes the files after copying (secure move). Accepts all the arguments that `scp` accepts.

```
usage: smv [-12346BCpqrv] [-c cipher] [-F ssh_config] [-i identity_file]
           [-l limit] [-o ssh_option] [-P port] [-S program]
           [[user@]host1:]file1 ... [[user@]host2:]file2
```

## ucwords

Performs title casing on strings. Accepts standard input. Typical use:

```bash
echo "my lowercase string needs some fixes" | ucwords
```
