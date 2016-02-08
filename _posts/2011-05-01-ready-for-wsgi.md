---
layout: page
title: Ready for WSGI
---

Here it is! Radicale is now ready to be launched behind your favourite HTTP
server (Apache, Lighttpd, Nginx or Tomcat for example). That's really good
news, because:

- Real HTTP servers are much more efficient and reliable than the default
  Python server used in Radicale;
- All the authentication backends available for your server will be available
  for Radicale;
- Thanks to [flup](http://trac.saddi.com/flup), Radicale can be interfaced
  with all the servers supporting CGI, AJP, FastCGI or SCGI;
- Radicale works very well without any additional server, without any
  dependencies, without configuration, just as it was working before;
- This one more feature removes useless code, less is definitely more.

The WSGI support has only be tested as a stand-alone executable and behind
Lighttpd, you should definitely try if it works with you favourite server too!

No more features will be added before (quite) a long time, because a lot of
documentation and test is waiting for us. If you want to write tutorials for
some CalDAV clients support (iCal, Android, iPhone), HTTP servers support or
logging management, feel free to fork the documentation git repository and ask
for a merge. It's plain text, I'm sure you can do it!
