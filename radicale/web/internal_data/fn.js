/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2017-2024 Unrud <unrud@outlook.com>
 * Copyright © 2023-2024 Matthew Hana <matthew.hana@gmail.com>
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
const SERVER = location.origin;

/**
 * Path of the root collection on the server (must end with /)
 * @const
 * @type {string}
 */
const ROOT_PATH = location.pathname.replace(new RegExp("/+[^/]+/*(/index\\.html?)?$"), "") + '/';

/**
 * Regex to match and normalize color
 * @const
 */
const COLOR_RE = new RegExp("^(#[0-9A-Fa-f]{6})(?:[0-9A-Fa-f]{2})?$");


/**
 * The text needed to confirm deleting a collection
 * @const
 */
const DELETE_CONFIRMATION_TEXT = "DELETE";

/**
 * Escape string for usage in XML
 * @param {string} s
 * @return {string}
 */
function escape_xml(s) {
    return (s
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&apos;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;"));
}

/**
 * @enum {string}
 */
const CollectionType = {
    PRINCIPAL: "PRINCIPAL",
    ADDRESSBOOK: "ADDRESSBOOK",
    CALENDAR_JOURNAL_TASKS: "CALENDAR_JOURNAL_TASKS",
    CALENDAR_JOURNAL: "CALENDAR_JOURNAL",
    CALENDAR_TASKS: "CALENDAR_TASKS",
    JOURNAL_TASKS: "JOURNAL_TASKS",
    CALENDAR: "CALENDAR",
    JOURNAL: "JOURNAL",
    TASKS: "TASKS",
    WEBCAL: "WEBCAL",
    is_subset: function(a, b) {
        let components = a.split("_");
        for (let i = 0; i < components.length; i++) {
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
        let union = [];
        if (a.search(this.CALENDAR) !== -1 || b.search(this.CALENDAR) !== -1) {
            union.push(this.CALENDAR);
        }
        if (a.search(this.JOURNAL) !== -1 || b.search(this.JOURNAL) !== -1) {
            union.push(this.JOURNAL);
        }
        if (a.search(this.TASKS) !== -1 || b.search(this.TASKS) !== -1) {
            union.push(this.TASKS);
        }
        if (a.search(this.WEBCAL) !== -1 || b.search(this.WEBCAL) !== -1) {
            union.push(this.WEBCAL);
        }
        return union.join("_");
    },
    valid_options_for_type: function(a){
        a = a.trim().toUpperCase();
        switch(a){
            case CollectionType.CALENDAR_JOURNAL_TASKS:
            case CollectionType.CALENDAR_JOURNAL:
            case CollectionType.CALENDAR_TASKS:
            case CollectionType.JOURNAL_TASKS:
            case CollectionType.CALENDAR:
            case CollectionType.JOURNAL:
            case CollectionType.TASKS:
                return [CollectionType.CALENDAR_JOURNAL_TASKS, CollectionType.CALENDAR_JOURNAL, CollectionType.CALENDAR_TASKS, CollectionType.JOURNAL_TASKS, CollectionType.CALENDAR, CollectionType.JOURNAL, CollectionType.TASKS];
            case CollectionType.ADDRESSBOOK:
            case CollectionType.WEBCAL:
            default:
                return [a];
        }
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
function Collection(href, type, displayname, description, color, contentcount, size, source) {
    this.href = href;
    this.type = type;
    this.displayname = displayname;
    this.color = color;
    this.description = description;
    this.source = source;
    this.contentcount = contentcount;
    this.size = size;
}

/**
 * Find the principal collection.
 * @param {string} user
 * @param {string} password
 * @param {function(?Collection, ?string)} callback Returns result or error
 * @return {XMLHttpRequest}
 */
function get_principal(user, password, callback) {
    let request = new XMLHttpRequest();
    request.open("PROPFIND", SERVER + ROOT_PATH, true, user, encodeURIComponent(password));
    request.onreadystatechange = function() {
        if (request.readyState !== 4) {
            return;
        }
        if (request.status === 207) {
            let xml = request.responseXML;
            let principal_element = xml.querySelector("*|multistatus:root > *|response:first-of-type > *|propstat > *|prop > *|current-user-principal > *|href");
            let displayname_element = xml.querySelector("*|multistatus:root > *|response:first-of-type > *|propstat > *|prop > *|displayname");
            if (principal_element) {
                callback(new Collection(
                    principal_element.textContent,
                    CollectionType.PRINCIPAL,
                    displayname_element ? displayname_element.textContent : "",
                    "",
                    0,
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
    let request = new XMLHttpRequest();
    request.open("PROPFIND", SERVER + collection.href, true, user, encodeURIComponent(password));
    request.setRequestHeader("depth", "1");
    request.onreadystatechange = function() {
        if (request.readyState !== 4) {
            return;
        }
        if (request.status === 207) {
            let xml = request.responseXML;
            let collections = [];
            let response_query = "*|multistatus:root > *|response";
            let responses = xml.querySelectorAll(response_query);
            for (let i = 0; i < responses.length; i++) {
                let response = responses[i];
                let href_element = response.querySelector(response_query + " > *|href");
                let resourcetype_query = response_query + " > *|propstat > *|prop > *|resourcetype";
                let resourcetype_element = response.querySelector(resourcetype_query);
                let displayname_element = response.querySelector(response_query + " > *|propstat > *|prop > *|displayname");
                let calendarcolor_element = response.querySelector(response_query + " > *|propstat > *|prop > *|calendar-color");
                let addressbookcolor_element = response.querySelector(response_query + " > *|propstat > *|prop > *|addressbook-color");
                let calendardesc_element = response.querySelector(response_query + " > *|propstat > *|prop > *|calendar-description");
                let addressbookdesc_element = response.querySelector(response_query + " > *|propstat > *|prop > *|addressbook-description");
                let contentcount_element = response.querySelector(response_query + " > *|propstat > *|prop > *|getcontentcount");
                let contentlength_element = response.querySelector(response_query + " > *|propstat > *|prop > *|getcontentlength");
                let webcalsource_element = response.querySelector(response_query + " > *|propstat > *|prop > *|source");
                let components_query = response_query + " > *|propstat > *|prop > *|supported-calendar-component-set";
                let components_element = response.querySelector(components_query);
                let href = href_element ? href_element.textContent : "";
                let displayname = displayname_element ? displayname_element.textContent : "";
                let type = "";
                let color = "";
                let description = "";
                let source = "";
                let count = 0;
                let size = 0;
                if (resourcetype_element) {
                    if (resourcetype_element.querySelector(resourcetype_query + " > *|addressbook")) {
                        type = CollectionType.ADDRESSBOOK;
                        color = addressbookcolor_element ? addressbookcolor_element.textContent : "";
                        description = addressbookdesc_element ? addressbookdesc_element.textContent : "";
                        count = contentcount_element ? parseInt(contentcount_element.textContent) : 0;
                        size = contentlength_element ? parseInt(contentlength_element.textContent) : 0;
                    } else if (resourcetype_element.querySelector(resourcetype_query + " > *|subscribed")) {
                        type = CollectionType.WEBCAL;
                        source = webcalsource_element ? webcalsource_element.textContent : "";
                        color = calendarcolor_element ? calendarcolor_element.textContent : "";
                        description = calendardesc_element ? calendardesc_element.textContent : "";
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
                        count = contentcount_element ? parseInt(contentcount_element.textContent) : 0;
                        size = contentlength_element ? parseInt(contentlength_element.textContent) : 0;
                    }
                }
                let sane_color = color.trim();
                if (sane_color) {
                    let color_match = COLOR_RE.exec(sane_color);
                    if (color_match) {
                        sane_color = color_match[1];
                    } else {
                        sane_color = "";
                    }
                }
                if (href.substr(-1) === "/" && href !== collection.href && type) {
                    collections.push(new Collection(href, type, displayname, description, sane_color, count, size, source));
                }
            }
            collections.sort(function(a, b) {
                /** @type {string} */ let ca = a.displayname || a.href;
                /** @type {string} */ let cb = b.displayname || b.href;
                return ca.localeCompare(cb);
            });
            callback(collections, null);
        } else {
            callback(null, request.status + " " + request.statusText);
        }
    };
    request.send('<?xml version="1.0" encoding="utf-8" ?>' +
                 '<propfind ' +
                         'xmlns="DAV:" ' +
                         'xmlns:C="urn:ietf:params:xml:ns:caldav" ' +
                         'xmlns:CR="urn:ietf:params:xml:ns:carddav" ' +
                         'xmlns:CS="http://calendarserver.org/ns/" ' +
                         'xmlns:I="http://apple.com/ns/ical/" ' +
                         'xmlns:INF="http://inf-it.com/ns/ab/" ' +
                         'xmlns:RADICALE="http://radicale.org/ns/"' +
                         '>' +
                     '<prop>' +
                         '<resourcetype />' +
                         '<RADICALE:displayname />' +
                         '<I:calendar-color />' +
                         '<INF:addressbook-color />' +
                         '<C:calendar-description />' +
                         '<C:supported-calendar-component-set />' +
                         '<CR:addressbook-description />' +
                         '<CS:source />' +
                         '<RADICALE:getcontentcount />' +
                         '<getcontentlength />' +
                     '</prop>' +
                 '</propfind>');
    return request;
}

/**
 * @param {string} user
 * @param {string} password
 * @param {string} collection_href Must always start and end with /.
 * @param {File} file
 * @param {function(?string)} callback Returns error or null
 * @return {XMLHttpRequest}
 */
function upload_collection(user, password, collection_href, file, callback) {
    let request = new XMLHttpRequest();
    request.open("PUT", SERVER + collection_href, true, user, encodeURIComponent(password));
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
    request.setRequestHeader("If-None-Match", "*");
    request.send(file);
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
    let request = new XMLHttpRequest();
    request.open("DELETE", SERVER + collection.href, true, user, encodeURIComponent(password));
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
    let request = new XMLHttpRequest();
    request.open(create ? "MKCOL" : "PROPPATCH", SERVER + collection.href, true, user, encodeURIComponent(password));
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
    let displayname = escape_xml(collection.displayname);
    let calendar_color = "";
    let addressbook_color = "";
    let calendar_description = "";
    let addressbook_description = "";
    let calendar_source = "";
    let resourcetype;
    let components = "";
    if (collection.type === CollectionType.ADDRESSBOOK) {
        addressbook_color = escape_xml(collection.color + (collection.color ? "ff" : ""));
        addressbook_description = escape_xml(collection.description);
        resourcetype = '<CR:addressbook />';
    } else if (collection.type === CollectionType.WEBCAL) {
        calendar_color = escape_xml(collection.color + (collection.color ? "ff" : ""));
        calendar_description = escape_xml(collection.description);
        resourcetype = '<CS:subscribed />';
        calendar_source = escape_xml(collection.source);
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
    let xml_request = create ? "mkcol" : "propertyupdate";
    request.send('<?xml version="1.0" encoding="UTF-8" ?>' +
                 '<' + xml_request + ' xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:CR="urn:ietf:params:xml:ns:carddav" xmlns:CS="http://calendarserver.org/ns/" xmlns:I="http://apple.com/ns/ical/" xmlns:INF="http://inf-it.com/ns/ab/">' +
                     '<set>' +
                         '<prop>' +
                             (create ? '<resourcetype><collection />' + resourcetype + '</resourcetype>' : '') +
                             (components ? '<C:supported-calendar-component-set>' + components + '</C:supported-calendar-component-set>' : '') +
                             (displayname ? '<displayname>' + displayname + '</displayname>' : '') +
                             (calendar_color ? '<I:calendar-color>' + calendar_color + '</I:calendar-color>' : '') +
                             (addressbook_color ? '<INF:addressbook-color>' + addressbook_color + '</INF:addressbook-color>' : '') +
                             (addressbook_description ? '<CR:addressbook-description>' + addressbook_description + '</CR:addressbook-description>' : '') +
                             (calendar_description ? '<C:calendar-description>' + calendar_description + '</C:calendar-description>' : '') +
                             (calendar_source ? '<CS:source>' + calendar_source + '</CS:source>' : '') +
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
 * @return {string}
*/
function random_uuid() {
    return random_hex(8) + "-" + random_hex(4) + "-" + random_hex(4) + "-" + random_hex(4) + "-" + random_hex(12);
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
let scene_stack = [];

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
        let old_length = scene_stack.length;
        scene_stack.pop().release();
        if (old_length - 1 === index + 1) {
            break;
        }
    }
    if (scene_stack.length >= 1) {
        let scene = scene_stack[scene_stack.length - 1];
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
    let html_scene = document.getElementById("loginscene");
    let form = html_scene.querySelector("[data-name=form]");
    let user_form = html_scene.querySelector("[data-name=user]");
    let password_form = html_scene.querySelector("[data-name=password]");
    let error_form = html_scene.querySelector("[data-name=error]");
    let logout_view = document.getElementById("logoutview");
    let logout_user_form = logout_view.querySelector("[data-name=user]");
    let logout_btn = logout_view.querySelector("[data-name=logout]");
    let refresh_btn = logout_view.querySelector("[data-name=refresh]");

    /** @type {?number} */ let scene_index = null;
    let user = "";
    let error = "";
    /** @type {?XMLHttpRequest} */ let principal_req = null;

    function read_form() {
        user = user_form.value;
    }

    function fill_form() {
        user_form.value = user;
        password_form.value = "";
        if(error){
            error_form.textContent = "Error: " + error;
            error_form.classList.remove("hidden");
        }else{
            error_form.classList.add("hidden");
        }
    }

    function onlogin() {
        try {
            read_form();
            let password = password_form.value;
            if (user) {
                error = "";
                // setup logout
                logout_view.classList.remove("hidden");
                logout_btn.onclick = onlogout;
                refresh_btn.onclick = refresh;
                logout_user_form.textContent = user + "'s Collections";
                // Fetch principal
                let loading_scene = new LoadingScene();
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
                        let saved_user = user;
                        user = "";
                        let collections_scene = new CollectionsScene(
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

    function remove_logout() {
        logout_view.classList.add("hidden");
        logout_btn.onclick = null;
        refresh_btn.onclick = null;
        logout_user_form.textContent = "";
    }

    function refresh(){
        //The easiest way to refresh is to push a LoadingScene onto the stack and then pop it
        //forcing the scene below it, the Collections Scene to refresh itself.
        push_scene(new LoadingScene(), false);
        pop_scene(scene_stack.length-2);
    }

    this.show = function() {
        remove_logout();
        fill_form();
        form.onsubmit = onlogin;
        html_scene.classList.remove("hidden");
        scene_index = scene_stack.length - 1;
        user_form.focus();
    };
    this.hide = function() {
        read_form();
        html_scene.classList.add("hidden");
        form.onsubmit = null;
    };
    this.release = function() {
        scene_index = null;
        // cancel pending requests
        if (principal_req !== null) {
            principal_req.abort();
            principal_req = null;
        }
        remove_logout();
    };
}

/**
 * @constructor
 * @implements {Scene}
 */
function LoadingScene() {
    let html_scene = document.getElementById("loadingscene");
    this.show = function() {
        html_scene.classList.remove("hidden");
    };
    this.hide = function() {
        html_scene.classList.add("hidden");
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
    let html_scene = document.getElementById("collectionsscene");
    let template = html_scene.querySelector("[data-name=collectiontemplate]");
    let new_btn = html_scene.querySelector("[data-name=new]");
    let upload_btn = html_scene.querySelector("[data-name=upload]");

    /** @type {?number} */ let scene_index = null;
    /** @type {?XMLHttpRequest} */ let collections_req = null;
    /** @type {?Array<Collection>} */ let collections = null;
    /** @type {Array<Node>} */ let nodes = [];

    function onnew() {
        try {
            let create_collection_scene = new CreateEditCollectionScene(user, password, collection);
            push_scene(create_collection_scene, false);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function onupload() {
        try {
            let upload_scene = new UploadCollectionScene(user, password, collection);
            push_scene(upload_scene);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function onedit(collection) {
        try {
            let edit_collection_scene = new CreateEditCollectionScene(user, password, collection);
            push_scene(edit_collection_scene, false);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function ondelete(collection) {
        try {
            let delete_collection_scene = new DeleteCollectionScene(user, password, collection);
            push_scene(delete_collection_scene, false);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function show_collections(collections) {
        let heightOfNavBar = document.querySelector("#logoutview").offsetHeight + "px";
        html_scene.style.marginTop = heightOfNavBar;
        html_scene.style.height = "calc(100vh - " + heightOfNavBar +")";
        collections.forEach(function (collection) {
            let node = template.cloneNode(true);
            node.classList.remove("hidden");
            let title_form = node.querySelector("[data-name=title]");
            let description_form = node.querySelector("[data-name=description]");
            let contentcount_form = node.querySelector("[data-name=contentcount]");
            let url_form = node.querySelector("[data-name=url]");
            let color_form = node.querySelector("[data-name=color]");
            let delete_btn = node.querySelector("[data-name=delete]");
            let edit_btn = node.querySelector("[data-name=edit]");
            let download_btn = node.querySelector("[data-name=download]");
            if (collection.color) {
                color_form.style.background = collection.color;
            }
            let possible_types = [CollectionType.ADDRESSBOOK, CollectionType.WEBCAL];
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
                    node.querySelector("[data-name=" + e + "]").classList.add("hidden");
                }
            });
            title_form.textContent = collection.displayname || collection.href;
            if(title_form.textContent.length > 30){
                title_form.classList.add("smalltext");
            }
            description_form.textContent = collection.description;
            if(description_form.textContent.length > 150){
                description_form.classList.add("smalltext");
            }
            if(collection.type != CollectionType.WEBCAL){
                let contentcount_form_txt = (collection.contentcount > 0 ? Number(collection.contentcount).toLocaleString() : "No") + " item" + (collection.contentcount == 1 ? "" : "s") + " in collection";
                if(collection.contentcount > 0){
                    contentcount_form_txt += " (" + bytesToHumanReadable(collection.size) + ")";
                }
                contentcount_form.textContent = contentcount_form_txt;
            }
            let href = SERVER + collection.href;
            url_form.value = href;
            download_btn.href = href;
            if(collection.type == CollectionType.WEBCAL){
                download_btn.parentElement.classList.add("hidden");
            }
            delete_btn.onclick = function() {return ondelete(collection);};
            edit_btn.onclick = function() {return onedit(collection);};
            node.classList.remove("hidden");
            nodes.push(node);
            template.parentNode.insertBefore(node, template);
        });
    }

    function update() {
        let loading_scene = new LoadingScene();
        push_scene(loading_scene, false);
        collections_req = get_collections(user, password, collection, function(collections1, error) {
            if (scene_index === null) {
                return;
            }
            collections_req = null;
            if (error) {
                onerror(error);
                pop_scene(scene_index - 1);
            } else {
                collections = collections1;
                pop_scene(scene_index);
            }
        });
    }

    this.show = function() {
        html_scene.classList.remove("hidden");
        new_btn.onclick = onnew;
        upload_btn.onclick = onupload;
        if (collections === null) {
            update();
        } else {
            // from update loading scene
            show_collections(collections);
        }
    };
    this.hide = function() {
        html_scene.classList.add("hidden");
        scene_index = scene_stack.length - 1;
        new_btn.onclick = null;
        upload_btn.onclick = null;
        collections = null;
        // remove collection
        nodes.forEach(function(node) {
            node.parentNode.removeChild(node);
        });
        nodes = [];
    };
    this.release = function() {
        scene_index = null;
        if (collections_req !== null) {
            collections_req.abort();
            collections_req = null;
        }
        collections = null;
    };
}

/**
 * @constructor
 * @implements {Scene}
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection parent collection
 * @param {Array<File>} files
 */
function UploadCollectionScene(user, password, collection) {
    let html_scene = document.getElementById("uploadcollectionscene");
    let template = html_scene.querySelector("[data-name=filetemplate]");
    let upload_btn = html_scene.querySelector("[data-name=submit]");
    let close_btn = html_scene.querySelector("[data-name=close]");
    let uploadfile_form = html_scene.querySelector("[data-name=uploadfile]");
    let uploadfile_lbl = html_scene.querySelector("label[for=uploadfile]");
    let href_form = html_scene.querySelector("[data-name=href]");
    let href_label = html_scene.querySelector("label[for=href]");
    let hreflimitmsg_html = html_scene.querySelector("[data-name=hreflimitmsg]");
    let pending_html = html_scene.querySelector("[data-name=pending]");

    let files = uploadfile_form.files;
    href_form.addEventListener("keydown", cleanHREFinput);
    upload_btn.onclick = upload_start;
    uploadfile_form.onchange = onfileschange;

    let href = random_uuid();
    href_form.value = href;

    /** @type {?number} */ let scene_index = null;
    /** @type {?XMLHttpRequest} */ let upload_req = null;
    /** @type {Array<string>} */ let results = [];
    /** @type {?Array<Node>} */ let nodes = null;

    function upload_start() {
        try {
            if(!read_form()){
                return false;
            }
            uploadfile_form.classList.add("hidden");
            uploadfile_lbl.classList.add("hidden");
            href_form.classList.add("hidden");
            href_label.classList.add("hidden");
            hreflimitmsg_html.classList.add("hidden");
            upload_btn.classList.add("hidden");
            close_btn.classList.add("hidden");

            pending_html.classList.remove("hidden");

            nodes = [];
            for (let i = 0; i < files.length; i++) {
                let file = files[i];
                let node = template.cloneNode(true);
                node.classList.remove("hidden");
                let name_form = node.querySelector("[data-name=name]");
                name_form.textContent = file.name;
                node.classList.remove("hidden");
                nodes.push(node);
                updateFileStatus(i);
                template.parentNode.insertBefore(node, template);
            }
            upload_next();
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function upload_next(){
        try{
            if (files.length === results.length) {
                pending_html.classList.add("hidden");
                close_btn.classList.remove("hidden");
                return;
            } else {
                let file = files[results.length];
                if(files.length > 1 || href.length == 0){
                    href = random_uuid();
                }
                let upload_href = collection.href + "/" + href + "/";
                upload_req = upload_collection(user, password, upload_href, file, function(result) {
                    upload_req = null;
                    results.push(result);
                    updateFileStatus(results.length - 1);
                    upload_next();
                });
            }
        }catch(err){
            console.error(err);
        }
    }

    function onclose() {
        try {
            pop_scene(scene_index - 1);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function updateFileStatus(i) {
        if (nodes === null) {
            return;
        }
        let success_form = nodes[i].querySelector("[data-name=success]");
        let error_form = nodes[i].querySelector("[data-name=error]");
        if (results.length > i) {
            if (results[i]) {
                success_form.classList.add("hidden");
                error_form.textContent = "Error: " + results[i];
                error_form.classList.remove("hidden");
            } else {
              success_form.classList.remove("hidden");
              error_form.classList.add("hidden");
            }
        } else {
            success_form.classList.add("hidden");
            error_form.classList.add("hidden");
        }
    }

    function read_form() {
        cleanHREFinput(href_form);
        let newhreftxtvalue = href_form.value.trim().toLowerCase();
        if(!isValidHREF(newhreftxtvalue)){
            alert("You must enter a valid HREF");
            return false;
        }
        href = newhreftxtvalue;

        if(uploadfile_form.files.length == 0){
            alert("You must select at least one file to upload");
            return false;
        }
        files = uploadfile_form.files;
        return true;
    }

    function onfileschange() {
        files = uploadfile_form.files;
        if(files.length > 1){
            hreflimitmsg_html.classList.remove("hidden");
            href_form.classList.add("hidden");
            href_label.classList.add("hidden");
        }else{
            hreflimitmsg_html.classList.add("hidden");
            href_form.classList.remove("hidden");
            href_label.classList.remove("hidden");
        }
        return false;
    }

    this.show = function() {
        scene_index = scene_stack.length - 1;
        html_scene.classList.remove("hidden");
        close_btn.onclick = onclose;
    };

    this.hide = function() {
        html_scene.classList.add("hidden");
        close_btn.classList.remove("hidden");
        upload_btn.classList.remove("hidden");
        uploadfile_form.classList.remove("hidden");
        uploadfile_lbl.classList.remove("hidden");
        href_form.classList.remove("hidden");
        href_label.classList.remove("hidden");
        hreflimitmsg_html.classList.add("hidden");
        pending_html.classList.add("hidden");
        close_btn.onclick = null;
        upload_btn.onclick = null;
        href_form.value = "";
        uploadfile_form.value = "";
        if(nodes == null){
            return;
        }
        nodes.forEach(function(node) {
            node.parentNode.removeChild(node);
        });
        nodes = null;
    };
    this.release = function() {
        scene_index = null;
        if (upload_req !== null) {
            upload_req.abort();
            upload_req = null;
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
    let html_scene = document.getElementById("deletecollectionscene");
    let title_form = html_scene.querySelector("[data-name=title]");
    let error_form = html_scene.querySelector("[data-name=error]");
    let confirmation_txt = html_scene.querySelector("[data-name=confirmationtxt]");
    let delete_confirmation_lbl = html_scene.querySelector("[data-name=deleteconfirmationtext]");
    let delete_btn = html_scene.querySelector("[data-name=delete]");
    let cancel_btn = html_scene.querySelector("[data-name=cancel]");

    delete_confirmation_lbl.innerHTML = DELETE_CONFIRMATION_TEXT;
    confirmation_txt.value = "";
    confirmation_txt.addEventListener("keydown", onkeydown);

    /** @type {?number} */ let scene_index = null;
    /** @type {?XMLHttpRequest} */ let delete_req = null;
    let error = "";

    function ondelete() {
        let confirmation_text_value = confirmation_txt.value;
        if(confirmation_text_value != DELETE_CONFIRMATION_TEXT){
            alert("Please type the confirmation text to delete this collection.");
            return;
        }
        try {
            let loading_scene = new LoadingScene();
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

    function onkeydown(event){
        if (event.keyCode !== 13) {
            return;
        }
        ondelete();
    }

    this.show = function() {
        this.release();
        scene_index = scene_stack.length - 1;
        html_scene.classList.remove("hidden");
        title_form.textContent = collection.displayname || collection.href;
        delete_btn.onclick = ondelete;
        cancel_btn.onclick = oncancel;
        if(error){
            error_form.textContent = "Error: " + error;
            error_form.classList.remove("hidden");
        }else{
            error_form.classList.add("hidden");
        }

    };
    this.hide = function() {
        html_scene.classList.add("hidden");
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
function random_hex(length) {
    let bytes = new Uint8Array(Math.ceil(length / 2));
    window.crypto.getRandomValues(bytes);
    return bytes.reduce((s, b) => s + b.toString(16).padStart(2, "0"), "").substring(0, length);
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
    let edit = collection.type !== CollectionType.PRINCIPAL;
    let html_scene = document.getElementById(edit ? "editcollectionscene" : "createcollectionscene");
    let title_form = edit ? html_scene.querySelector("[data-name=title]") : null;
    let error_form = html_scene.querySelector("[data-name=error]");
    let href_form = html_scene.querySelector("[data-name=href]");
    let href_label = html_scene.querySelector("label[for=href]");
    let displayname_form = html_scene.querySelector("[data-name=displayname]");
    let displayname_label = html_scene.querySelector("label[for=displayname]");
    let description_form = html_scene.querySelector("[data-name=description]");
    let description_label = html_scene.querySelector("label[for=description]");
    let source_form = html_scene.querySelector("[data-name=source]");
    let source_label = html_scene.querySelector("label[for=source]");
    let type_form = html_scene.querySelector("[data-name=type]");
    let type_label = html_scene.querySelector("label[for=type]");
    let color_form = html_scene.querySelector("[data-name=color]");
    let color_label = html_scene.querySelector("label[for=color]");
    let submit_btn = html_scene.querySelector("[data-name=submit]");
    let cancel_btn = html_scene.querySelector("[data-name=cancel]");


    /** @type {?number} */ let scene_index = null;
    /** @type {?XMLHttpRequest} */ let create_edit_req = null;
    let error = "";
    /** @type {?Element} */ let saved_type_form = null;

    let href = edit ? collection.href : collection.href + random_uuid() + "/";
    let displayname = edit ? collection.displayname : "";
    let description = edit ? collection.description : "";
    let source = edit ? collection.source : "";
    let type = edit ? collection.type : CollectionType.CALENDAR_JOURNAL_TASKS;
    let color = edit && collection.color ? collection.color : "#" + random_hex(6);

    if(!edit){
        href_form.addEventListener("keydown", cleanHREFinput);
    }

    function remove_invalid_types() {
        if (!edit) {
            return;
        }
        /** @type {HTMLOptionsCollection} */ let options = type_form.options;
        // remove all options that are not supersets
        let valid_type_options = CollectionType.valid_options_for_type(type);
        for (let i = options.length - 1; i >= 0; i--) {
            if (valid_type_options.indexOf(options[i].value) < 0) {
                options.remove(i);
            }
        }
    }

    function read_form() {
        if(!edit){
            cleanHREFinput(href_form);
            let newhreftxtvalue = href_form.value.trim().toLowerCase();
            if(!isValidHREF(newhreftxtvalue)){
                alert("You must enter a valid HREF");
                return false;
            }
            href = collection.href + "/" + newhreftxtvalue + "/";
        }
        displayname = displayname_form.value;
        description = description_form.value;
        source = source_form.value;
        type = type_form.value;
        color = color_form.value;
        return true;
    }

    function fill_form() {
        if(!edit){
            href_form.value = random_uuid();
        }
        displayname_form.value = displayname;
        description_form.value = description;
        source_form.value = source;
        type_form.value = type;
        color_form.value = color;
        if(error){
            error_form.textContent = "Error: " + error;
            error_form.classList.remove("hidden");
        }
        error_form.classList.add("hidden");
        onTypeChange();
        type_form.addEventListener("change", onTypeChange);
    }

    function onsubmit() {
        try {
            if(!read_form()){
                return false;
            }
            let sane_color = color.trim();
            if (sane_color) {
                let color_match = COLOR_RE.exec(sane_color);
                if (!color_match) {
                    error = "Invalid color";
                    fill_form();
                    return false;
                }
                sane_color = color_match[1];
            }
            let loading_scene = new LoadingScene();
            push_scene(loading_scene);
            let collection = new Collection(href, type, displayname, description, sane_color, 0, 0, source);
            let callback = function(error1) {
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


    function onTypeChange(e){
        if(type_form.value == CollectionType.WEBCAL){
            source_label.classList.remove("hidden");
            source_form.classList.remove("hidden");
        }else{
            source_label.classList.add("hidden");
            source_form.classList.add("hidden");
        }
    }

    this.show = function() {
        this.release();
        scene_index = scene_stack.length - 1;
        // Clone type_form because it's impossible to hide options without removing them
        saved_type_form = type_form;
        type_form = type_form.cloneNode(true);
        saved_type_form.parentNode.replaceChild(type_form, saved_type_form);
        remove_invalid_types();
        html_scene.classList.remove("hidden");
        if (edit) {
            title_form.textContent = collection.displayname || collection.href;
        }
        fill_form();
        submit_btn.onclick = onsubmit;
        cancel_btn.onclick = oncancel;
    };
    this.hide = function() {
        read_form();
        html_scene.classList.add("hidden");
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

/**
 * Removed invalid HREF characters for a collection HREF.
 *
 * @param a A valid Input element or an onchange Event of an Input element.
 */
function cleanHREFinput(a) {
    let href_form = a;
    if (a.target) {
        href_form = a.target;
    }
    let currentTxtVal = href_form.value.trim().toLowerCase();
    //Clean the HREF to remove non lowercase letters and dashes
    currentTxtVal = currentTxtVal.replace(/(?![0-9a-z\-\_])./g, '');
    href_form.value = currentTxtVal;
}

/**
 * Checks if a proposed HREF for a collection has a valid format and syntax.
 *
 * @param href String of the porposed HREF.
 *
 * @return Boolean results if the HREF is valid.
 */
function isValidHREF(href) {
    if (href.length < 1) {
        return false;
    }
    if (href.indexOf("/") != -1) {
        return false;
    }

    return true;
}

/**
 * Format bytes to human-readable text.
 *
 * @param bytes Number of bytes.
 *
 * @return Formatted string.
 */
function bytesToHumanReadable(bytes, dp=1) {
    let isNumber = !isNaN(parseFloat(bytes)) && !isNaN(bytes - 0);
    if(!isNumber){
        return "";
    }
    var i = bytes == 0 ? 0 : Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(dp) * 1 + ' ' + ['b', 'kb', 'mb', 'gb', 'tb'][i];
}


function main() {
    // Hide startup loading message
    document.getElementById("loadingscene").classList.add("hidden");
    push_scene(new LoginScene(), false);
}

window.addEventListener("load", main);
