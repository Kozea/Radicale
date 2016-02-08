---
layout: page
title: HTTPS and Authentication
---

HTTPS connections and authentication have been added to Radicale this
week. Command-line options and personal configuration files are also ready for
test. According to the TODO file included in the package, the next version will
finally be 0.2, when sunbird 1.0 is out. Go, Mozilla hackers, go!

HTTPS connection
  HTTPS connections are now available using the standard TLS mechanisms. Give
  Radicale a private key and a certificate, and your data are now safe.

Authentication
  A simple authentication architecture is now available, allowing different
  methods thanks to different modules. The first two modules are ``fake`` (no
  authentication) and ``htpasswd`` (authentication with an ``htpasswd`` file
  created by the Apache tool). More methods such as LDAP are coming soon!
