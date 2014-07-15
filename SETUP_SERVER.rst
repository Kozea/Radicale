This is how to run the server on AppEngine:

The first time you run the server, create empty collections by directing you browser to:

/collections/create

=========
Local development server
=========

Install the Google AppEngine SDK for python (https://developers.google.com/appengine/downloads).

> GoogleAppEnginelauncher
> File
> Add Exiting Application

Then:

path = <is the root of the project, where the app.yaml is>
admin port = 8000 <or whatever you like>
port = 8080 <or whatever you like>

You can then run the project using:

> Control
> Run

Your server is running at:

http://localhost:8080

(remember to create empty collections, see at top)

=========
Production
=========

Create a Google AppEngine account.

Go to: https://appengine.google.com/

> Create Application

Application identifier = radicale-gae <choose something else that's available, make sure it matches your application name in app.yaml>
Application Title = Radicale AppEngine <does not matter>

leave auth options as is

> Create Application

then use GoogleAppEnginelauncher (instructions above) to deploy:

 > Control
 > Deploy
 
 (remember to create empty collections, see at top)
 
Your server is running at:

https://radicale-gae.appspot.com

http requests will be automatically redirected to https

(remember to create empty collections, see at top)