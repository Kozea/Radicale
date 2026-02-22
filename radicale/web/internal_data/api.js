/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2017-2024 Unrud <unrud@outlook.com>
 * Copyright © 2023-2024 Matthew Hana <matthew.hana@gmail.com>
 * Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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

import { Collection, CollectionType } from "./models.js";
import { SERVER, ROOT_PATH, COLOR_RE } from "./constants.js";
import { escape_xml } from "./utils.js";

export let server_features = {};

/**
 * Find the principal collection.
 * @param {string} user
 * @param {string} password
 * @param {function(?Collection, ?string)} callback Returns result or error
 * @return {XMLHttpRequest}
 */
export function get_principal(user, password, callback) {
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
export function get_collections(user, password, collection, callback) {
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
export function upload_collection(user, password, collection_href, file, callback) {
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
export function delete_collection(user, password, collection, callback) {
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
export function create_collection(user, password, collection, callback) {
    return create_edit_collection(user, password, collection, true, callback);
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection
 * @param {function(?string)} callback Returns error or null
 * @return {XMLHttpRequest}
 */
export function edit_collection(user, password, collection, callback) {
    return create_edit_collection(user, password, collection, false, callback);
}
/* Sharing API */

function call_sharing_api(
  user,
  password,
  path,
  body,
  on_success,
  on_not_found = null,
  on_error = null,
) {
  let request = new XMLHttpRequest();
  request.open(
    "POST",
    SERVER + ROOT_PATH + ".sharing/v1/" + path,
    true,
    user,
    encodeURIComponent(password),
  );
  request.onreadystatechange = function () {
    if (request.readyState !== 4) {
      return;
    }
    if (200 <= request.status && request.status < 300) {
      on_success(request.responseText);
    } else if (request.status === 404) {
      if (on_not_found) {
        on_not_found();
      } else if (on_error) {
        on_error("Not found");
      } else {
        console.error("Not found");
      }
    } else {
      if (on_error) {
        on_error(request.status + " " + request.statusText);
      } else {
        console.error(request.status + " " + request.statusText);
      }
    }
  };
  request.setRequestHeader("Accept", "application/json");
  request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
  request.send(body ? JSON.stringify(body) : null);
  return request;
}

export function discover_server_features(user, password, callback) {
  call_sharing_api(
    user,
    password,
    "all/info",
    {},
    function (response) {
      server_features["sharing"] = JSON.parse(response);
      callback();
    },
    function () {
      // sharing is disabled on the server
      server_features["sharing"] = {};
      callback();
    },
    function (error) {
      console.error("Failed to discover sharing features: " + error);
    },
  );
}

export function reload_sharing_list(user, password, collection, callback) {
  call_sharing_api(
    user,
    password,
    "all/list",
    { PathMapped: collection.href },
    function (response) {
      callback(JSON.parse(response));
    },
  );
}

export function add_share_by_token(
  user,
  password,
  collection,
  permissions,
  callback,
) {
  call_sharing_api(
    user,
    password,
    "token/create",
    {
      PathMapped: collection.href,
      Permissions: permissions,
    },
    function (response) {
        let json_response = JSON.parse(response);
        if (json_response["Status"] !== "success") {
            console.error("Failed to create share token: " + (json_response["Status"] || "Unknown error"));
        } else {
            callback();
        }
    },
  );
}

export function delete_share_by_token(
  user,
  password,
  token,
  callback,
) {
  call_sharing_api(
    user,
    password,
    "token/delete",
    { PathOrToken: token },
    function (response) {
        let json_response = JSON.parse(response);
        if (json_response["Status"] !== "success") {
            console.error("Failed to create delete token " + token + ": " + (json_response["Status"] || "Unknown error"));
        } else {
            callback();
        }
    },
  );
}
