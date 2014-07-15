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

                return self.response.write("collections have been created ")

            if path=='collections/delete':
            
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

        return self.response.write("You have requested:\n\n%s\n\nImagine some content there... The CardDAV/CalDAv endpoint is: /sync"%path)

WSGI = webapp2.WSGIApplication([webapp2.Route(r'<path:.*>', handler=MainHandler)],
                               debug=True)

import radicale
WSGI_Radicale = radicale.Application()
radicale.log.start() # do not forget to start the logs