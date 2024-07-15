# VAEVA - vendor agnostic EV analytics

`vaeva` fetches EV charging data for multiple users and chargers. 

The following chargers are supported:
- [Wallbox](https://wallbox.com)
- [Easee](https://easee.com)

This data can then be formatted using `jinja2` templates. Output files can be rendered as text files (for `csv`, `json` or `xml` outputs) or as PDF files for printable reports.

## Installation

Install in own virtual environment.

```bash
$ python3 -m venv venv
$ source venv/bin/activate
$ (venv) pip3 install -r requirements.txt
```

## Usage

```
vaeva [-h] [-s SITE] [-u USER] [-o OUTPUT] [-c CONFIG] begin end

Vendor agnostic EV analytics

positional arguments:
  begin                 Begin date (bom, bolm or dateparser format)
  end                   End date (eolm or dateparser format)

options:
  -h, --help            show this help message and exit
  -s SITE, --site SITE  Site to process, default is all sites
  -u USER, --user USER  User to process, default is all users
  -o OUTPUT, --output OUTPUT
                        Outputs to generate, default is all outputs
  -c CONFIG, --config CONFIG
                        Full path of the config file, default is vaeva.yml
```

