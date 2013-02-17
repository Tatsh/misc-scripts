# Miscellaneous scripts

Random scripts I make and might still use.

## chrome-import-cookies

Imports cookies from a file in Netscape 'cookies.txt' format into Chromium's (Chrome) 'Default' user database. For Linux only at the moment.

Usage: `./chrome-import-cookies COOKIES_TXT_FILE`

## linkshare-dec

Given a Linkshare affilate URL, this decodes the target URL and displays it.

Usage: `./linkshare-dec URL`

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
