'''
main handler and route definition
'''

# python
import logging
logging.basicConfig(level=logging.DEBUG)

# GAE
import webapp2

class MainHandler(webapp2.RequestHandler):
    
    def propfind(self, path):
        # allow propfind requests so we don't have to specify a server path when setting up WebDAV clients
        logging.critical('Redirecting from propfind path='+str(path))
        return self.redirect('/sync')

    def get(self, path):
        self.response.headers['Content-Type'] = 'text/plain'
        
        path = path.strip('/')

        if path.startswith('collections'): 
            import radicale.storage.appengine
            
            if path=='collections/create':
                #return self.response.write("(disabled)")
                
                radicale.storage.appengine.Collection('test').create()
                radicale.storage.appengine.Collection('test/contacts.vcf').create()
                radicale.storage.appengine.Collection('test/events.ics').create()

                return self.response.write("collections have been created ")

            if path=='collections/delete':
                #return self.response.write("(disabled)")
            
                radicale.storage.appengine.Collection('test/contacts.vcf').delete()
                radicale.storage.appengine.Collection('test/contacts.vcf').delete_items()
                radicale.storage.appengine.Collection('test/events.ics').delete()
                radicale.storage.appengine.Collection('test/events.ics').delete_items()
                radicale.storage.appengine.Collection('test').delete()
                
                return self.response.write("collections have been deleted ")

            if path=='collections/list':
                
                out = []
                
                for collection_container in radicale.storage.appengine.CollectionContainerAppengine.query():                    
                    out.append( '* COLLECTION: key=%s:\nprops=%s' % (', '.join([str(pair) for pair in collection_container.key.pairs()]), collection_container.props) )
                    out.append( 'events='+str(collection_container.events.keys()) )
                    out.append( 'cards='+str(collection_container.cards.keys()) )
                    out.append( 'todos='+str(collection_container.todos.keys()) )
                    out.append( 'journals='+str(collection_container.journals.keys()) )
                    out.append( 'timezones='+str(collection_container.timezones.keys()) )
                    out.append( '\n\n' )
 
                for item_container in radicale.storage.appengine.ItemContainerAppengine.query():                    
                    out.append( '* item: key=%s\ntag=%s\ntext:\n%s' % (', '.join([str(pair) for pair in item_container.key.pairs()]), item_container.item_tag, item_container.item_text) )
                    out.append( '\n\n' )
                
                return self.response.write('\n'.join(out))

        return self.response.write("You have requested:\n\n%s\n\nWe could serve any page we like here... Go to /collections/list for an image of the datastore."%path)

# monkey patching webapp2 to handle exotic methods (to allow for redirects to the correct handler)
for extra_method in ['PROPFIND']:
    if not extra_method in webapp2.WSGIApplication.allowed_methods:
        webapp2.WSGIApplication.allowed_methods = set( tuple(webapp2.WSGIApplication.allowed_methods) + (extra_method,) )
    
WSGI = webapp2.WSGIApplication([webapp2.Route(r'<path:.*>', handler=MainHandler)],
                               debug=True)

import radicale
WSGI_Radicale = radicale.Application()
radicale.log.start() # do not forget to start the logs