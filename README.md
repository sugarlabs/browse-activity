What is this?
=============

Browse is a web browser activity for the Sugar desktop.

How to use?
===========

Browse is part of the Sugar desktop and is always included.  Please refer to;

* [How to Get Sugar on sugarlabs.org](https://sugarlabs.org/),
* [How to use Sugar](https://help.sugarlabs.org/), and;
* [How to use Browse](https://help.sugarlabs.org/en/browse.html).

How to upgrade?
===============

On Sugar desktop systems;
* use [My Settings](https://help.sugarlabs.org/en/my_settings.html), [Software Update](https://help.sugarlabs.org/en/my_settings.html#software-update), or;
* use Browse to open [activities.sugarlabs.org](https://activities.sugarlabs.org/), search for `Browse`, then download.

How to integrate?
=================

On Debian and Ubuntu systems;

```
apt install sugar-browse-activity
```

On Fedora systems;

```
dnf install sugar-browse
```

Browse depends on Python, [Sugar
Toolkit](https://github.com/sugarlabs/sugar-toolkit-gtk3), D-Bus,
Cairo, Telepathy, GTK+ 3, Pango, Rsvg, Soup, Evince and WebKit.
Unusually, Browse also depends on `glib-compile-schemas` to
compile a Gio.Settings schema.

Browse is started by [Sugar](https://github.com/sugarlabs/sugar).

Browse is packaged by Linux distributions;
* [Debian package sugar-browse-activity](https://packages.debian.org/sugar-browse-activity),
* [Ubuntu package sugar-browse-activity](https://packages.ubuntu.com/sugar-browse-activity), and;
* [Fedora package sugar-browse](https://src.fedoraproject.org/).

How to develop?
===============

* setup a development environment for Sugar desktop,
* clone this repository,
* edit source files,
* test in Terminal by typing `sugar-activity3`

APIs
====

Code inside Browse depends on several APIs, including;

* [PyGObject](https://lazka.github.io/pgi-docs/), and;
* [Sugar Toolkit](https://developer.sugarlabs.org/sugar3).

Branch master
=============

The `master` branch targets an environment with latest stable release
of [Sugar](https://github.com/sugarlabs/sugar), with dependencies on
latest stable release of Fedora and Debian distributions.

Release tags are v204 and higher.

Branch python2
==============

The `python2` branch is a backport of features and bug fixes from the
`master` branch for ongoing maintenance of the activity on Ubuntu
16.04 and Ubuntu 18.04 systems which don't have a Python 3 capable
release of Sugar.

Release tags are v203.2 and higher, but lower than v204.

Branch not-webkit2
==================

The `not-webkit2` branch is a backport of features and bug fixes from
the `master` branch for ongoing maintenance of the activity on Fedora
18 systems which don't have well-functioning WebKit2 packages.

Release tags are v157.5 and higher, but lower than v200.
