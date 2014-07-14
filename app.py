'''
main handler and route definition
'''

# python
import logging
logging.basicConfig(level=logging.DEBUG)

# GAE
import webapp2

class MainHandler(webapp2.RequestHandler):

    def get(self, path):
        self.response.headers['Content-Type'] = 'text/plain'
        
        path = path.strip('/')

        if path.startswith('collections'): 
            import radicale.storage.appengine
            
            if path=='collections/create':
                
                radicale.storage.appengine.Collection('test').create()
                radicale.storage.appengine.Collection('test/contacts.vcf').create()
                radicale.storage.appengine.Collection('test/events.ics').create()

#                 radicale.storage.appengine.Collection('test').create( props={"tag": "(node)"} )
#                 radicale.storage.appengine.Collection('test/contacts.vcf').create( props={"tag": "VADDRESSBOOK"} )
#                 radicale.storage.appengine.Collection('test/events.ics').create( props={"tag": "VCALENDAR"} )
                
                return self.response.write("collections have been created ")

            if path=='collections/delete':
            
                raise NotImplementedError

            if path=='collections/see':
                
                out = []
                
                for collection_container in radicale.storage.appengine.CollectionContainerAppengine.query():
                    
                    out.append( 'collection: key=%s:\nprops=%s' % ('/'.join([id for kind, id in collection_container.key.pairs()]), collection_container.props) )
                
                return self.response.write("all items:\n\n"+'\n\n'.join(out))
                
            if path=='collections/list':
                
                out = []
                
                for item_container in radicale.storage.appengine.ItemContainerAppengine.query():
                    
                    out.append( 'item: key=%s (tag=%s):\n%s' % ('/'.join([id for kind, id in item_container.key.pairs()]), item_container.item_tag, item_container.item_text) )
                
                return self.response.write("all items:\n\n"+'\n\n'.join(out))

        return self.response.write("You have requested:\n\n%s\n\nImagine some content there... The CardDAV/CalDAv endpoint is: /sync"%path)

WSGI = webapp2.WSGIApplication([webapp2.Route(r'<path:.*>', handler=MainHandler)],
                               debug=True)

import radicale
WSGI_Radicale = radicale.Application()
radicale.log.start() # do not forget to start the logs