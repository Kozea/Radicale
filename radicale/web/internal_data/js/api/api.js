/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2017-2024 Unrud <unrud@outlook.com>
 * Copyright © 2023-2024 Matthew Hana <matthew.hana@gmail.com>
 * Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
 * Copyright © 2026-2026 Max Berger <max@berger.name>
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

import { COLOR_RE, ROOT_PATH, SERVER } from "../constants.js";
import { Collection, CollectionType } from "../models/collection.js";
import { escape_xml } from "../utils/misc.js";
import { create_request, to_error_message } from "./common.js";

/**
 * Find the principal collection.
 * @param {?string} user
 * @param {?string} password
 * @param {function(?Collection, ?string):void} callback Returns result or error
 * @return {XMLHttpRequest}
 */
export function get_principal(user, password, callback) {
    let request = create_request("PROPFIND", SERVER + ROOT_PATH, user, password);
    request.onreadystatechange = function () {
        if (request.readyState !== 4) {
            return;
        }
        if (request.status === 207) {
            let xml = request.responseXML;
            if (xml) {
                let principal_element = xml.querySelector("*|multistatus:root > *|response:first-of-type > *|propstat > *|prop > *|current-user-principal > *|href");
                let displayname_element = xml.querySelector("*|multistatus:root > *|response:first-of-type > *|propstat > *|prop > *|displayname");
                let version_element = xml.querySelector("*|multistatus:root > *|response:first-of-type > *|propstat > *|prop > *|version");
                if (principal_element) {
                    callback(new Collection(
                        principal_element.textContent,
                        CollectionType.PRINCIPAL,
                        displayname_element ? displayname_element.textContent : "",
                        "",
                        "",
                        0,
                        0,
                        "",
                        [],
                        version_element ? version_element.textContent : ""), null,);
                } else {
                    callback(null, "No valid XML received")
                }
            } else {
                callback(null, "Internal error");
            }
        } else {
            callback(null, to_error_message(request));
        }
    };
    request.send('<?xml version="1.0" encoding="utf-8" ?>' +
        '<propfind xmlns="DAV:" xmlns:RADICALE="http://radicale.org/ns/">' +
        '<prop>' +
        '<current-user-principal />' +
        '<displayname />' +
        '<RADICALE:version />' +
        '</prop>' +
        '</propfind>');
    return request;
}

/**
 * Find all calendars and addressbooks in collection.
 * @param {string} user
 * @param {?string} password
 * @param {Collection} collection
 * @param {function(?Array<Collection>, ?string):void} callback Returns result or error
 * @return {XMLHttpRequest}
 */
export function get_collections(user, password, collection, callback) {
    let request = create_request("PROPFIND", SERVER + collection.href, user, password);
    request.setRequestHeader("depth", "1");
    request.onreadystatechange = function () {
        if (request.readyState !== 4) {
            return;
        }
        if (request.status === 207) {
            let xml = request.responseXML;
            if (xml) {
                let collections = [];
                let response_query = "*|multistatus:root > *|response";
                let responses = xml.querySelectorAll(response_query);
                for (let i = 0; i < responses.length; i++) {
                    let parsedCollection = _parse_collection(responses[i], collection.href);
                    if (parsedCollection) {
                        collections.push(parsedCollection);
                    }
                }
                collections.sort(function (a, b) {
                    /** @type {string} */ let ca = a.displayname || a.href;
                    /** @type {string} */ let cb = b.displayname || b.href;
                    return ca.localeCompare(cb);
                });
                callback(collections, null);
            } else {
                callback(null, "No valid XML received");
            }
        } else {
            callback(null, to_error_message(request));
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
        '<current-user-privilege-set />' +
        '</prop>' +
        '</propfind>');
    return request;
}

/**
 * Parses permissions from the current-user-privilege-set element.
 * @param {Element|null} current_user_privilege_set_element 
 * @returns {Array<string>}
 */
function _parse_permissions(current_user_privilege_set_element) {
    if (!current_user_privilege_set_element) return [];
    let permissions = [];
    let privileges = current_user_privilege_set_element.querySelectorAll("*|privilege");
    for (let j = 0; j < privileges.length; j++) {
        let privilege = privileges[j];
        let privilege_children = privilege.children;
        for (let k = 0; k < privilege_children.length; k++) {
            let child = privilege_children[k];
            let prefix = "D:";
            if (child.namespaceURI) {
                if (child.namespaceURI === "DAV:") {
                    prefix = "D:";
                } else if (child.namespaceURI === "http://radicale.org/ns/") {
                    prefix = "RADICALE:";
                } else {
                    prefix = child.namespaceURI + ":";
                }
            } else if (child.nodeName.includes(":")) {
                prefix = ""; // nodeName already contains prefix
            }
            let permName = child.localName || child.nodeName;
            if (!permName.includes(":")) {
                permName = prefix + permName;
            }
            permissions.push(permName);
        }
    }
    return permissions;
}

/**
 * Parses a single response element into a Collection object.
 * @param {Element} response 
 * @param {string} collection_href 
 * @returns {Collection|null}
 */
function _parse_collection(response, collection_href) {
    let href_element = response.querySelector("*|href");
    let current_user_privilege_set_element = response.querySelector("*|propstat > *|prop > *|current-user-privilege-set");
    let resourcetype_element = response.querySelector("*|propstat > *|prop > *|resourcetype");
    let displayname_element = response.querySelector("*|propstat > *|prop > *|displayname");

    let href = href_element ? href_element.textContent : "";
    let displayname = displayname_element ? displayname_element.textContent : "";
    let type = "";
    let color = "";
    let description = "";
    let source = "";
    let count = 0;
    let size = 0;
    let permissions = _parse_permissions(current_user_privilege_set_element);

    if (resourcetype_element) {
        if (resourcetype_element.querySelector("*|addressbook")) {
            type = CollectionType.ADDRESSBOOK;
            let addressbookcolor_element = response.querySelector("*|propstat > *|prop > *|addressbook-color");
            let addressbookdesc_element = response.querySelector("*|propstat > *|prop > *|addressbook-description");
            let contentcount_element = response.querySelector("*|propstat > *|prop > *|getcontentcount");
            let contentlength_element = response.querySelector("*|propstat > *|prop > *|getcontentlength");

            color = addressbookcolor_element ? addressbookcolor_element.textContent : "";
            description = addressbookdesc_element ? addressbookdesc_element.textContent : "";
            count = contentcount_element ? parseInt(contentcount_element.textContent, 10) : 0;
            size = contentlength_element ? parseInt(contentlength_element.textContent, 10) : 0;
            if (isNaN(count)) count = 0;
            if (isNaN(size)) size = 0;
        } else if (resourcetype_element.querySelector("*|subscribed")) {
            type = CollectionType.WEBCAL;
            let webcalsource_element = response.querySelector("*|propstat > *|prop > *|source");
            let calendarcolor_element = response.querySelector("*|propstat > *|prop > *|calendar-color");
            let calendardesc_element = response.querySelector("*|propstat > *|prop > *|calendar-description");

            source = webcalsource_element ? webcalsource_element.textContent : "";
            color = calendarcolor_element ? calendarcolor_element.textContent : "";
            description = calendardesc_element ? calendardesc_element.textContent : "";
        } else if (resourcetype_element.querySelector("*|calendar")) {
            let components_element = response.querySelector("*|propstat > *|prop > *|supported-calendar-component-set");
            if (components_element) {
                if (components_element.querySelector("*|comp[name=VEVENT]")) {
                    type = CollectionType.union(type, CollectionType.CALENDAR);
                }
                if (components_element.querySelector("*|comp[name=VJOURNAL]")) {
                    type = CollectionType.union(type, CollectionType.JOURNAL);
                }
                if (components_element.querySelector("*|comp[name=VTODO]")) {
                    type = CollectionType.union(type, CollectionType.TASKS);
                }
            }
            let calendarcolor_element = response.querySelector("*|propstat > *|prop > *|calendar-color");
            let calendardesc_element = response.querySelector("*|propstat > *|prop > *|calendar-description");
            let contentcount_element = response.querySelector("*|propstat > *|prop > *|getcontentcount");
            let contentlength_element = response.querySelector("*|propstat > *|prop > *|getcontentlength");

            color = calendarcolor_element ? calendarcolor_element.textContent : "";
            description = calendardesc_element ? calendardesc_element.textContent : "";
            count = contentcount_element ? parseInt(contentcount_element.textContent, 10) : 0;
            size = contentlength_element ? parseInt(contentlength_element.textContent, 10) : 0;
            if (isNaN(count)) count = 0;
            if (isNaN(size)) size = 0;
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

    if (href.endsWith("/") && href !== collection_href && type) {
        return new Collection(href, type, displayname, description, sane_color, count, size, source, permissions, "");
    }
    return null;
}

/**
 * @param {string} user
 * @param {?string} password
 * @param {string} collection_href Must always start and end with /.
 * @param {File} file
 * @param {function(?string):void} callback Returns error or null
 * @return {XMLHttpRequest}
 */
export function upload_collection(user, password, collection_href, file, callback) {
    let request = create_request("PUT", SERVER + collection_href, user, password);
    request.onreadystatechange = function () {
        if (request.readyState !== 4) {
            return;
        }
        if (200 <= request.status && request.status < 300) {
            callback(null);
        } else {
            callback(to_error_message(request));
        }
    };
    request.setRequestHeader("If-None-Match", "*");
    request.send(file);
    return request;
}

/**
 * @param {string} user
 * @param {?string} password
 * @param {Collection} collection
 * @param {function(?string):void} callback Returns error or null
 * @return {XMLHttpRequest}
 */
export function delete_collection(user, password, collection, callback) {
    let request = create_request("DELETE", SERVER + collection.href, user, password);
    request.onreadystatechange = function () {
        if (request.readyState !== 4) {
            return;
        }
        if (200 <= request.status && request.status < 300) {
            callback(null);
        } else {
            callback(to_error_message(request));
        }
    };
    request.send();
    return request;
}

/**
 * @param {string} user
 * @param {?string} password
 * @param {Collection} collection
 * @param {boolean} create
 * @param {function(?string):void} callback Returns error or null
 * @return {XMLHttpRequest}
 */
function create_edit_collection(user, password, collection, create, callback) {
    let request = create_request(create ? "MKCOL" : "PROPPATCH", SERVER + collection.href, user, password);
    request.onreadystatechange = function () {
        if (request.readyState !== 4) {
            return;
        }
        if (200 <= request.status && request.status < 300) {
            callback(null);
        } else {
            callback(to_error_message(request));
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
            '</remove>') : '') +
        '</' + xml_request + '>');
    return request;
}

/**
 * @param {string} user
 * @param {?string} password
 * @param {Collection} collection
 * @param {function(?string):void} callback Returns error or null
 * @return {XMLHttpRequest}
 */
export function create_collection(user, password, collection, callback) {
    return create_edit_collection(user, password, collection, true, callback);
}

/**
 * @param {string} user
 * @param {?string} password
 * @param {Collection} collection
 * @param {function(?string):void} callback Returns error or null
 * @return {XMLHttpRequest}
 */
export function edit_collection(user, password, collection, callback) {
    return create_edit_collection(user, password, collection, false, callback);
}

