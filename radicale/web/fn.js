/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright (C) 2017 Unrud <unrud@openaliasbox.org>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

/**
 * Server address
 * @const
 * @type {string}
 */
var SERVER = (location.protocol + '//' + location.hostname +
              (location.port ? ':' + location.port : ''));

/**
 * Path of the root collection on the server (must end with /)
 * @const
 * @type {string}
 */
var ROOT_PATH = location.pathname.replace(new RegExp("/+[^/]+/*(/index\\.html?)?$"), "") + '/';

/**
 * time between updates of collections (milliseconds)
 * @const
  * @type {?int}
 */
var UPDATE_INTERVAL = null;

/**
 * Regex to match and normalize color
 * @const
 */
var COLOR_RE = new RegExp("^(#[0-9A-Fa-f]{6})(?:[0-9A-Fa-f]{2})?$");

/**
 * Escape string for usage in XML
 * @param {string} s
 * @return {string}
 */
function escape_xml(s) {
    return (s
            .replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"));
}

/**
 * @enum {string}
 */
var CollectionType = {
    PRINCIPAL: "PRINCIPAL",
    ADDRESSBOOK: "ADDRESSBOOK",
    CALENDAR_JOURNAL_TASKS: "CALENDAR_JOURNAL_TASKS",
    CALENDAR_JOURNAL: "CALENDAR_JOURNAL",
    CALENDAR_TASKS: "CALENDAR_TASKS",
    JOURNAL_TASKS: "JOURNAL_TASKS",
    CALENDAR: "CALENDAR",
    JOURNAL: "JOURNAL",
    TASKS: "TASKS",
    is_subset: function(a, b) {
        var components = a.split("_");
        var i;
        for (i = 0; i < components.length; i++) {
            if (b.search(components[i]) === -1) {
                return false;
            }
        }
        return true;
    },
    union: function(a, b) {
        if (a.search(this.ADDRESSBOOK) !== -1 || b.search(this.ADDRESSBOOK) !== -1) {
            if (a && a !== this.ADDRESSBOOK || b && b !== this.ADDRESSBOOK) {
                throw "Invalid union: " + a + " " + b;
            }
            return this.ADDRESSBOOK;
        }
        var union = "";
        if (a.search(this.CALENDAR) !== -1 || b.search(this.CALENDAR) !== -1) {
            union += (union ? "_" : "") + this.CALENDAR;
        }
        if (a.search(this.JOURNAL) !== -1 || b.search(this.JOURNAL) !== -1) {
            union += (union ? "_" : "") + this.JOURNAL;
        }
        if (a.search(this.TASKS) !== -1 || b.search(this.TASKS) !== -1) {
            union += (union ? "_" : "") + this.TASKS;
        }
        return union;
    }
};

/**
 * @constructor
 * @struct
 * @param {string} href Must always start and end with /.
 * @param {CollectionType} type
 * @param {string} displayname
 * @param {string} description
 * @param {string} color
 */
function Collection(href, type, displayname, description, color) {
    this.href = href;
    this.type = type;
    this.displayname = displayname;
    this.color = color;
    this.description = description;
}

/**
 * Find the principal collection.
 * @param {string} user
 * @param {string} password
 * @param {function(?Collection, ?string)} callback Returns result or error
 * @return {XMLHttpRequest}
 */
function get_principal(user, password, callback) {
    var request = new XMLHttpRequest();
    request.open("PROPFIND", SERVER + ROOT_PATH, true, user, password);
    request.onreadystatechange = function() {
        if (request.readyState !== 4) {
            return;
        }
        if (request.status === 207) {
            var xml = request.responseXML;
            var principal_element = xml.querySelector("*|multistatus:root > *|response:first-of-type > *|propstat > *|prop > *|current-user-principal > *|href");
            var displayname_element = xml.querySelector("*|multistatus:root > *|response:first-of-type > *|propstat > *|prop > *|displayname");
            if (principal_element) {
                callback(new Collection(
                    principal_element.textContent,
                    CollectionType.PRINCIPAL,
                    displayname_element ? displayname_element.textContent : "",
                    "",
                    ""), null);
            } else {
                callback(null, "Internal error");
            }
        } else {
            callback(null, request.status + " " + request.statusText);
        }
    };
    request.send('<?xml version="1.0" encoding="utf-8" ?>' +
                 '<propfind xmlns="DAV:">' +
                     '<prop>' +
                         '<current-user-principal />' +
                         '<displayname />' +
                     '</prop>' +
                 '</propfind>');
    return request;
}

/**
 * Find all calendars and addressbooks in collection.
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection
 * @param {function(?Array<Collection>, ?string)} callback Returns result or error
 * @return {XMLHttpRequest}
 */
function get_collections(user, password, collection, callback) {
    var request = new XMLHttpRequest();
    request.open("PROPFIND", SERVER + collection.href, true, user, password);
    request.setRequestHeader("depth", "1");
    request.onreadystatechange = function() {
        if (request.readyState !== 4) {
            return;
        }
        if (request.status === 207) {
            var xml = request.responseXML;
            var collections = [];
            var response_query = "*|multistatus:root > *|response";
            var responses = xml.querySelectorAll(response_query);
            var i;
            for (i = 0; i < responses.length; i++) {
                var response = responses[i];
                var href_element = response.querySelector(response_query + " > *|href");
                var resourcetype_query = response_query + " > *|propstat > *|prop > *|resourcetype";
                var resourcetype_element = response.querySelector(resourcetype_query);
                var displayname_element = response.querySelector(response_query + " > *|propstat > *|prop > *|displayname");
                var calendarcolor_element = response.querySelector(response_query + " > *|propstat > *|prop > *|calendar-color");
                var addressbookcolor_element = response.querySelector(response_query + " > *|propstat > *|prop > *|addressbook-color");
                var calendardesc_element = response.querySelector(response_query + " > *|propstat > *|prop > *|calendar-description");
                var addressbookdesc_element = response.querySelector(response_query + " > *|propstat > *|prop > *|addressbook-description");
                var components_query = response_query + " > *|propstat > *|prop > *|supported-calendar-component-set";
                var components_element = response.querySelector(components_query);
                var href = href_element ? href_element.textContent : "";
                var displayname = displayname_element ? displayname_element.textContent : "";
                var type = "";
                var color = "";
                var description = "";
                if (resourcetype_element) {
                    if (resourcetype_element.querySelector(resourcetype_query + " > *|addressbook")) {
                        type = CollectionType.ADDRESSBOOK;
                        color = addressbookcolor_element ? addressbookcolor_element.textContent : "";
                        description = addressbookdesc_element ? addressbookdesc_element.textContent : "";
                    } else if (resourcetype_element.querySelector(resourcetype_query + " > *|calendar")) {
                        if (components_element) {
                            if (components_element.querySelector(components_query + " > *|comp[name=VEVENT]")) {
                                type = CollectionType.union(type, CollectionType.CALENDAR);
                            }
                            if (components_element.querySelector(components_query + " > *|comp[name=VJOURNAL]")) {
                                type = CollectionType.union(type, CollectionType.JOURNAL);
                            }
                            if (components_element.querySelector(components_query + " > *|comp[name=VTODO]")) {
                                type = CollectionType.union(type, CollectionType.TASKS);
                            }
                        }
                        color = calendarcolor_element ? calendarcolor_element.textContent : "";
                        description = calendardesc_element ? calendardesc_element.textContent : "";
                    }
                }
                var sane_color = color.trim();
                if (sane_color) {
                    var color_match = COLOR_RE.exec(sane_color);
                    if (color_match) {
                        sane_color = color_match[1];
                    } else {
                        sane_color = "";
                    }
                }
                if (href.substr(-1) === "/" && href !== collection.href && type) {
                    collections.push(new Collection(href, type, displayname, description, sane_color));
                }
            }
            collections.sort(function(a, b) {
                /** @type {string} */ var ca = a.displayname || a.href;
                /** @type {string} */ var cb = b.displayname || b.href;
                return ca.localeCompare(cb);
            });
            callback(collections, null);
        } else {
            callback(null, request.status + " " + request.statusText);
        }
    };
    request.send('<?xml version="1.0" encoding="utf-8" ?>' +
                 '<propfind xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" ' +
                         'xmlns:CR="urn:ietf:params:xml:ns:carddav" ' +
                         'xmlns:I="http://apple.com/ns/ical/" ' +
                         'xmlns:INF="http://inf-it.com/ns/ab/" ' +
                         'xmlns:RADICALE="http://radicale.org/ns/">' +
                     '<prop>' +
                         '<resourcetype />' +
                         '<RADICALE:displayname />' +
                         '<I:calendar-color />' +
                         '<INF:addressbook-color />' +
                         '<C:calendar-description />' +
                         '<C:supported-calendar-component-set />' +
                         '<CR:addressbook-description />' +
                     '</prop>' +
                 '</propfind>');
    return request;
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection
 * @param {function(?string)} callback Returns error or null
 * @return {XMLHttpRequest}
 */
function delete_collection(user, password, collection, callback) {
    var request = new XMLHttpRequest();
    request.open("DELETE", SERVER + collection.href, true, user, password);
    request.onreadystatechange = function() {
        if (request.readyState !== 4) {
            return;
        }
        if (200 <= request.status && request.status < 300) {
            callback(null);
        } else {
            callback(request.status + " " + request.statusText);
        }
    };
    request.send();
    return request;
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection
 * @param {boolean} create
 * @param {function(?string)} callback Returns error or null
 * @return {XMLHttpRequest}
 */
function create_edit_collection(user, password, collection, create, callback) {
    var request = new XMLHttpRequest();
    request.open(create ? "MKCOL" : "PROPPATCH", SERVER + collection.href, true, user, password);
    request.onreadystatechange = function() {
        if (request.readyState !== 4) {
            return;
        }
        if (200 <= request.status && request.status < 300) {
            callback(null);
        } else {
            callback(request.status + " " + request.statusText);
        }
    };
    var displayname = escape_xml(collection.displayname);
    var calendar_color = "";
    var addressbook_color = "";
    var calendar_description = "";
    var addressbook_description = "";
    var resourcetype;
    var components = "";
    if (collection.type === CollectionType.ADDRESSBOOK) {
        addressbook_color = escape_xml(collection.color + (collection.color ? "ff" : ""));
        addressbook_description = escape_xml(collection.description);
        resourcetype = '<CR:addressbook />';
    } else {
        calendar_color = escape_xml(collection.color + (collection.color ? "ff" : ""));
        calendar_description = escape_xml(collection.description);
        resourcetype = '<C:calendar />';
        if (CollectionType.is_subset(CollectionType.CALENDAR, collection.type)) {
            components += '<C:comp name="VEVENT" />';
        }
        if (CollectionType.is_subset(CollectionType.JOURNAL, collection.type)) {
            components += '<C:comp name="VJOURNAL" />';
        }
        if (CollectionType.is_subset(CollectionType.TASKS, collection.type)) {
            components += '<C:comp name="VTODO" />';
        }
    }
    var xml_request = create ? "mkcol" : "propertyupdate";
    request.send('<?xml version="1.0" encoding="UTF-8" ?>' +
                 '<' + xml_request + ' xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:CR="urn:ietf:params:xml:ns:carddav" xmlns:I="http://apple.com/ns/ical/" xmlns:INF="http://inf-it.com/ns/ab/">' +
                     '<set>' +
                         '<prop>' +
                             (create ? '<resourcetype><collection />' + resourcetype + '</resourcetype>' : '') +
                             (components ? '<C:supported-calendar-component-set>' + components + '</C:supported-calendar-component-set>' : '') +
                             (displayname ? '<displayname>' + displayname + '</displayname>' : '') +
                             (calendar_color ? '<I:calendar-color>' + calendar_color + '</I:calendar-color>' : '') +
                             (addressbook_color ? '<INF:addressbook-color>' + addressbook_color + '</INF:addressbook-color>' : '') +
                             (addressbook_description ? '<CR:addressbook-description>' + addressbook_description + '</CR:addressbook-description>' : '') +
                             (calendar_description ? '<C:calendar-description>' + calendar_description + '</C:calendar-description>' : '') +
                         '</prop>' +
                     '</set>' +
                     (!create ? ('<remove>' +
                         '<prop>' +
                             (!components ? '<C:supported-calendar-component-set />' : '') +
                             (!displayname ? '<displayname />' : '') +
                             (!calendar_color ? '<I:calendar-color />' : '') +
                             (!addressbook_color ? '<INF:addressbook-color />' : '') +
                             (!addressbook_description ? '<CR:addressbook-description />' : '') +
                             (!calendar_description ? '<C:calendar-description />' : '') +
                         '</prop>' +
                     '</remove>'): '') +
                 '</' + xml_request + '>');
    return request;
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection
 * @param {function(?string)} callback Returns error or null
 * @return {XMLHttpRequest}
 */
function create_collection(user, password, collection, callback) {
    return create_edit_collection(user, password, collection, true, callback);
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection
 * @param {function(?string)} callback Returns error or null
 * @return {XMLHttpRequest}
 */
function edit_collection(user, password, collection, callback) {
    return create_edit_collection(user, password, collection, false, callback);
}

/**
 * @interface
 */
function Scene() {}
/**
 * Scene is on top of stack and visible.
 */
Scene.prototype.show = function() {};
/**
 * Scene is no longer visible.
 */
Scene.prototype.hide = function() {};
/**
 * Scene is removed from scene stack.
 */
Scene.prototype.release = function() {};


/**
 * @type {Array<Scene>}
 */
var scene_stack = [];

/**
 * Push scene onto stack.
 * @param {Scene} scene
 * @param {boolean} replace Replace the scene on top of the stack.
 */
function push_scene(scene, replace) {
    if (scene_stack.length >= 1) {
        scene_stack[scene_stack.length - 1].hide();
        if (replace) {
            scene_stack.pop().release();
        }
    }
    scene_stack.push(scene);
    scene.show();
}

/**
 * Remove scenes from stack.
 * @param {number} index New top of stack
 */
function pop_scene(index) {
    if (scene_stack.length - 1 <= index) {
        return;
    }
    scene_stack[scene_stack.length - 1].hide();
    while (scene_stack.length - 1 > index) {
        var old_length = scene_stack.length;
        scene_stack.pop().release();
        if (old_length - 1 === index + 1) {
            break;
        }
    }
    if (scene_stack.length >= 1) {
        var scene = scene_stack[scene_stack.length - 1];
        scene.show();
    } else {
        throw "Scene stack is empty";
    }
}

/**
 * @constructor
 * @implements {Scene}
 */
function LoginScene() {
    var html_scene = document.getElementById("loginscene");
    var form = html_scene.querySelector("[name=form]");
    var user_form = html_scene.querySelector("[name=user]");
    var password_form = html_scene.querySelector("[name=password]");
    var error_form = html_scene.querySelector("[name=error]");
    var logout_view = document.getElementById("logoutview");
    var logout_user_form = logout_view.querySelector("[name=user]");
    var logout_btn = logout_view.querySelector("[name=link]");
    var first_show = true;

    /** @type {?number} */ var scene_index = null;
    var user = "";
    var error = "";
    /** @type {?XMLHttpRequest} */ var principal_req = null;

    function read_form() {
        user = user_form.value;
    }

    function fill_form() {
        user_form.value = user;
        password_form.value = "";
        error_form.textContent = error ? "Error: " + error : "";
    }

    function onlogin() {
        try {
            read_form();
            var password = password_form.value;
            if (user) {
                error = "";
                // setup logout
                logout_view.style.display = "block";
                logout_btn.onclick = onlogout;
                logout_user_form.textContent = user;
                // Fetch principal
                var loading_scene = new LoadingScene();
                push_scene(loading_scene, false);
                principal_req = get_principal(user, password, function(collection, error1) {
                    if (scene_index === null) {
                        return;
                    }
                    principal_req = null;
                    if (error1) {
                        error = error1;
                        pop_scene(scene_index);
                    } else {
                        // show collections
                        var saved_user = user;
                        user = "";
                        if (typeof(sessionStorage) !== "undefined") {
                            sessionStorage.setItem("radicale_user", saved_user);
                            sessionStorage.setItem("radicale_password", password);
                        }
                        var collections_scene = new CollectionsScene(
                            saved_user, password, collection, function(error1) {
                                error = error1;
                                user = saved_user;
                            });
                        push_scene(collections_scene, true);
                    }
                });
            } else {
                error = "Username is empty";
                fill_form();
            }
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function onlogout() {
        try {
            if (scene_index === null) {
                return false;
            }
            user = "";
            pop_scene(scene_index);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    this.show = function() {
        var saved_first_show = first_show;
        first_show = false;
        this.release();
        fill_form();
        form.onsubmit = onlogin;
        html_scene.style.display = "block";
        user_form.focus();
        scene_index = scene_stack.length - 1;
        if (typeof(sessionStorage) !== "undefined") {
            if (saved_first_show && sessionStorage.getItem("radicale_user")) {
                user_form.value = sessionStorage.getItem("radicale_user");
                password_form.value = sessionStorage.getItem("radicale_password");
                onlogin();
            } else {
                sessionStorage.setItem("radicale_user", "");
                sessionStorage.setItem("radicale_password", "");
            }
        }
    };
    this.hide = function() {
        read_form();
        html_scene.style.display = "none";
        form.onsubmit = null;
    };
    this.release = function() {
        scene_index = null;
        // cancel pending requests
        if (principal_req !== null) {
            principal_req.abort();
            principal_req = null;
        }
        // remove logout
        logout_view.style.display = "none";
        logout_btn.onclick = null;
        logout_user_form.textContent = "";
    };
}

/**
 * @constructor
 * @implements {Scene}
 */
function LoadingScene() {
    var html_scene = document.getElementById("loadingscene");
    this.show = function() {
        html_scene.style.display = "block";
    };
    this.hide = function() {
        html_scene.style.display = "none";
    };
    this.release = function() {};
}

/**
 * @constructor
 * @implements {Scene}
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection The principal collection.
 * @param {function(string)} onerror Called when an error occurs, before the
 *                                   scene is popped.
 */
function CollectionsScene(user, password, collection, onerror) {
    var html_scene = document.getElementById("collectionsscene");
    var template = html_scene.querySelector("[name=collectiontemplate]");
    var new_btn = html_scene.querySelector("[name=new]");

    /** @type {?number} */ var scene_index = null;
    var saved_template_display = null;
    /** @type {?XMLHttpRequest} */ var collections_req = null;
    var timer = null;
    var from_update = false;
    /** @type {?Array<Collection>} */ var collections = null;
    /** @type {Array<Node>} */ var nodes = [];

    function onnew() {
        try {
            var create_collection_scene = new CreateEditCollectionScene(user, password, collection);
            push_scene(create_collection_scene, false);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function onedit(collection) {
        try {
            var edit_collection_scene = new CreateEditCollectionScene(user, password, collection);
            push_scene(edit_collection_scene, false);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function ondelete(collection) {
        try {
            var delete_collection_scene = new DeleteCollectionScene(user, password, collection);
            push_scene(delete_collection_scene, false);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function show_collections(collections) {
        nodes.forEach(function(node) {
            template.parentNode.removeChild(node);
        });
        nodes = [];
        collections.forEach(function (collection) {
            var node = template.cloneNode(true);
            var title_form = node.querySelector("[name=title]");
            var description_form = node.querySelector("[name=description]");
            var url_form = node.querySelector("[name=url]");
            var color_form = node.querySelector("[name=color]");
            var delete_btn = node.querySelector("[name=delete]");
            var edit_btn = node.querySelector("[name=edit]");
            if (collection.color) {
                color_form.style.color = collection.color;
            } else {
                color_form.style.display = "none";
            }
            var possible_types = [CollectionType.ADDRESSBOOK];
            [CollectionType.CALENDAR, ""].forEach(function(e) {
                [CollectionType.union(e, CollectionType.JOURNAL), e].forEach(function(e) {
                    [CollectionType.union(e, CollectionType.TASKS), e].forEach(function(e) {
                        if (e) {
                            possible_types.push(e);
                        }
                    });
                });
            });
            possible_types.forEach(function(e) {
                if (e !== collection.type) {
                    node.querySelector("[name=" + e + "]").style.display = "none";
                }
            });
            title_form.textContent = collection.displayname || collection.href;
            description_form.textContent = collection.description;
            var href = SERVER + collection.href;
            url_form.href = href;
            url_form.textContent = href;
            delete_btn.onclick = function(ev) {return ondelete(collection);};
            edit_btn.onclick = function(ev) {return onedit(collection);};
            node.style.display = saved_template_display;
            nodes.push(node);
            template.parentNode.insertBefore(node, template);
        });
    }

    function update() {
        if (collections === null) {
            var loading_scene = new LoadingScene();
            push_scene(loading_scene, false);
        }
        collections_req = get_collections(user, password, collection, function(collections1, error) {
            if (scene_index === null) {
                return;
            }
            collections_req = null;
            if (error) {
                onerror(error);
                pop_scene(scene_index - 1);
            } else {
                var old_collections = collections;
                collections = collections1;
                if (UPDATE_INTERVAL !== null) {
                    timer = window.setTimeout(update, UPDATE_INTERVAL);
                }
                from_update = true;
                if (old_collections === null) {
                    pop_scene(scene_index);
                } else {
                    show_collections(collections);
                }
            }
        });
    }

    this.show = function() {
        saved_template_display = template.style.display;
        template.style.display = "none";
        html_scene.style.display = "block";
        new_btn.onclick = onnew;
        if (scene_index === null) {
            scene_index = scene_stack.length - 1;
            if (collections === null && collections_req !== null) {
                pop_scene(scene_index - 1);
                return;
            }
            update();
        } else if (collections === null) {
            pop_scene(scene_index - 1);
        } else {
            if (from_update) {
                show_collections(collections);
            } else {
                collections = null;
                update();
            }
        }
    };
    this.hide = function() {
        html_scene.style.display = "none";
        template.style.display = saved_template_display;
        new_btn.onclick = null;
        if (timer !== null) {
            window.clearTimeout(timer);
            timer = null;
        }
        from_update = false;
        if (collections !== null && collections_req !== null) {
            collections_req.abort();
            collections_req = null;
        }
        show_collections([]);
    };
    this.release = function() {
        scene_index = null;
        if (collections_req !== null) {
            collections_req.abort();
            collections_req = null;
        }
    };
}

/**
 * @constructor
 * @implements {Scene}
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection
 */
function DeleteCollectionScene(user, password, collection) {
    var html_scene = document.getElementById("deletecollectionscene");
    var title_form = html_scene.querySelector("[name=title]");
    var error_form = html_scene.querySelector("[name=error]");
    var delete_btn = html_scene.querySelector("[name=delete]");
    var cancel_btn = html_scene.querySelector("[name=cancel]");
    var no_btn = html_scene.querySelector("[name=no]");

    /** @type {?number} */ var scene_index = null;
    /** @type {?XMLHttpRequest} */ var delete_req = null;
    var error = "";

    function ondelete() {
        try {
            var loading_scene = new LoadingScene();
            push_scene(loading_scene);
            delete_req = delete_collection(user, password, collection, function(error1) {
                if (scene_index === null) {
                    return;
                }
                delete_req = null;
                if (error1) {
                    error = error1;
                    pop_scene(scene_index);
                } else {
                    pop_scene(scene_index - 1);
                }
            });
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function oncancel() {
        try {
            pop_scene(scene_index - 1);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    this.show = function() {
        this.release();
        scene_index = scene_stack.length - 1;
        html_scene.style.display = "block";
        title_form.textContent = collection.displayname || collection.href;
        error_form.textContent = error ? "Error: " + error : "";
        delete_btn.onclick = ondelete;
        cancel_btn.onclick = oncancel;
    };
    this.hide = function() {
        html_scene.style.display = "none";
        cancel_btn.onclick = null;
        delete_btn.onclick = null;
    };
    this.release = function() {
        scene_index = null;
        if (delete_req !== null) {
            delete_req.abort();
            delete_req = null;
        }
    };
}

/**
 * Generate random hex number.
 * @param {number} length
 * @return {string}
 */
function randHex(length) {
    var s = Math.floor(Math.random() * Math.pow(16, length)).toString(16);
    while (s.length < length) {
        s = "0" + s;
    }
    return s;
}

/**
 * @constructor
 * @implements {Scene}
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection if it's a principal collection, a new
 *                                collection will be created inside of it.
 *                                Otherwise the collection will be edited.
 */
function CreateEditCollectionScene(user, password, collection) {
    var edit = collection.type !== CollectionType.PRINCIPAL;
    var html_scene = document.getElementById(edit ? "editcollectionscene" : "createcollectionscene");
    var title_form = edit ? html_scene.querySelector("[name=title]") : null;
    var error_form = html_scene.querySelector("[name=error]");
    var displayname_form = html_scene.querySelector("[name=displayname]");
    var description_form = html_scene.querySelector("[name=description]");
    var type_form = html_scene.querySelector("[name=type]");
    var color_form = html_scene.querySelector("[name=color]");
    var submit_btn = html_scene.querySelector("[name=submit]");
    var cancel_btn = html_scene.querySelector("[name=cancel]");

    /** @type {?number} */ var scene_index = null;
    /** @type {?XMLHttpRequest} */ var create_edit_req = null;
    var error = "";
    /** @type {?Element} */ var saved_type_form = null;

    var href = edit ? collection.href : (
        collection.href + randHex(8) + "-" + randHex(4) + "-" + randHex(4) +
        "-" + randHex(4) + "-" + randHex(12) + "/");
    var displayname = edit ? collection.displayname : "";
    var description = edit ? collection.description : "";
    var type = edit ? collection.type : CollectionType.CALENDAR_JOURNAL_TASKS;
    var color = edit && collection.color ? collection.color : "#" + randHex(6);

    function remove_invalid_types() {
        if (!edit) {
            return;
        }
        /** @type {HTMLOptionsCollection} */ var options = type_form.options;
        // remove all options that are not supersets
        var i;
        for (i = options.length - 1; i >= 0; i--) {
            if (!CollectionType.is_subset(type, options[i].value)) {
                options.remove(i);
            }
        }
    }

    function read_form() {
        displayname = displayname_form.value;
        description = description_form.value;
        type = type_form.value;
        color = color_form.value;
    }

    function fill_form() {
        displayname_form.value = displayname;
        description_form.value = description;
        type_form.value = type;
        color_form.value = color;
        error_form.textContent = error ? "Error: " + error : "";
    }

    function onsubmit() {
        try {
            read_form();
            var sane_color = color.trim();
            if (sane_color) {
                var color_match = COLOR_RE.exec(sane_color);
                if (!color_match) {
                    error = "Invalid color";
                    fill_form();
                    return false;
                }
                sane_color = color_match[1];
            }
            var loading_scene = new LoadingScene();
            push_scene(loading_scene);
            var collection = new Collection(href, type, displayname, description, sane_color);
            var callback = function(error1) {
                if (scene_index === null) {
                    return;
                }
                create_edit_req = null;
                if (error1) {
                    error = error1;
                    pop_scene(scene_index);
                } else {
                    pop_scene(scene_index - 1);
                }
            };
            if (edit) {
                create_edit_req = edit_collection(user, password, collection, callback);
            } else {
                create_edit_req = create_collection(user, password, collection, callback);
            }
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function oncancel() {
        try {
            pop_scene(scene_index - 1);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    this.show = function() {
        this.release();
        scene_index = scene_stack.length - 1;
        // Clone type_form because it's impossible to hide options without removing them
        saved_type_form = type_form;
        type_form = type_form.cloneNode(true);
        saved_type_form.parentNode.replaceChild(type_form, saved_type_form);
        remove_invalid_types();
        html_scene.style.display = "block";
        if (edit) {
            title_form.textContent = collection.displayname || collection.href;
        }
        fill_form();
        submit_btn.onclick = onsubmit;
        cancel_btn.onclick = oncancel;
    };
    this.hide = function() {
        read_form();
        html_scene.style.display = "none";
        // restore type_form
        type_form.parentNode.replaceChild(saved_type_form, type_form);
        type_form = saved_type_form;
        saved_type_form = null;
        submit_btn.onclick = null;
        cancel_btn.onclick = null;
    };
    this.release = function() {
        scene_index = null;
        if (create_edit_req !== null) {
            create_edit_req.abort();
            create_edit_req = null;
        }
    };
}

function main() {
    push_scene(new LoginScene(), false);
}

window.addEventListener("load", main);
