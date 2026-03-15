/**
 * This file is part of Radicale Server - Calendar Server
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

import { ROOT_PATH, SERVER } from "../constants.js";
import { CollectionType } from "../models/collection.js";

/**
 * @typedef {Object} SharingFeatures
 * @property {number} [ApiVersion]
 * @property {string} [Status]
 * @property {boolean} [FeatureEnabledCollectionByMap]
 * @property {boolean} [PermittedCreateCollectionByMap]
 * @property {boolean} [FeatureEnabledCollectionByToken]
 * @property {boolean} [PermittedCreateCollectionByToken]
 */

/**
 * @typedef {Object} ServerFeatures
 * @property {SharingFeatures} [sharing]
 */

/**
 * @param {string} user
 * @param {string} password
 * @param {string} path
 * @param {object} body
 * @param {function(string):void} on_success
 * @param {function():void} on_not_found
 * @param {function(string):void} on_error
 * @returns {XMLHttpRequest}
 */
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

/**
 * @param {string} user
 * @param {string} password
 * @param {function(import("../api/sharing.js").ServerFeatures, ?string):void} callback
 */
export function discover_server_features(user, password, callback) {
    call_sharing_api(
        user,
        password,
        "all/info",
        {},
        function (response) {
            try {
                let features = { "sharing": JSON.parse(response) };
                callback(features, null);
            } catch (e) {
                callback({}, e.message);
            }
        },
        function () {
            // sharing is disabled on the server
            callback({ "sharing": {} }, null);
        },
        function (error) {
            callback({}, error);
        },
    );
}

export class Share {
    /**
     * @param {Object} [data]
     */
    constructor(data = {}) {
        /** @type {string} */ this.ShareType = data.ShareType || "";
        /** @type {string} */ this.PathOrToken = data.PathOrToken || "";
        /** @type {string} */ this.PathMapped = data.PathMapped || "";
        /** @type {string} */ this.Owner = data.Owner || "";
        /** @type {string} */ this.User = data.User || "";
        /** @type {string} */ this.Permissions = data.Permissions || "r";
        /** @type {boolean} */ this.EnabledByOwner = data.EnabledByOwner ?? data.Enabled ?? false;
        /** @type {?boolean} */ this.EnabledByUser = data.EnabledByUser ?? data.Enabled ?? null;
        /** @type {boolean} */ this.HiddenByOwner = data.HiddenByOwner ?? data.Hidden ?? false;
        /** @type {?boolean} */ this.HiddenByUser = data.HiddenByUser ?? data.Hidden ?? null;
        /** @type {number} */ this.TimestampCreated = data.TimestampCreated || 0;
        /** @type {number} */ this.TimestampUpdated = data.TimestampUpdated || 0;
        /** @type {Object} */ this.Properties = data.Properties || {};
    }
}

/**
 * @param {string} user
 * @param {string} password
 * @param {import("../models/collection.js").Collection} collection
 * @param {function(Array<Share>, ?string):void} callback
 */
export function reload_sharing_list(user, password, collection, callback) {
    let body = collection ? { PathMapped: collection.href } : {};
    return call_sharing_api(
        user,
        password,
        "all/list",
        body,
        function (response) {
            let parsed = JSON.parse(response);
            let shares = (parsed["Content"] || []).map(data => new Share(data));
            callback(shares, null);
        },
        null, // on_not_found
        function (error) {
            callback([], error);
        },
    );
}

/**
 * Property keys for different collection types.
 * Map to OVERLAY_PROPERTIES_WHITELIST in radicale/sharing/__init__.py
 */
export const OVERLAY_PROPERTIES = {
    CALENDAR: {
        DESCRIPTION: "C:calendar-description",
        COLOR: "ICAL:calendar-color",
    },
    ADDRESSBOOK: {
        DESCRIPTION: "CR:addressbook-description",
        COLOR: "INF:addressbook-color",
    }
};

/**
 * Returns the correct internal property key for a given collection type and property name.
 * @param {string} type Collection type (ADDRESSBOOK, CALENDAR, etc.)
 * @param {"DESCRIPTION" | "COLOR"} property Property name
 * @returns {string | null} Internal property key or null if not supported
 */
export function get_property_key(type, property) {
    if (type === CollectionType.ADDRESSBOOK) {
        return OVERLAY_PROPERTIES.ADDRESSBOOK[property];
    } else if (CollectionType.is_subset(CollectionType.CALENDAR, type)) {
        return OVERLAY_PROPERTIES.CALENDAR[property];
    }
    return null;
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Share} share
 * @param {function(?string):void} callback
 */
export function add_share_by_token(
    user,
    password,
    share,
    callback,
) {
    call_sharing_api(
        user,
        password,
        "token/create",
        {
            PathMapped: share.PathMapped,
            Permissions: share.Permissions,
            Enabled: share.EnabledByOwner,
            Hidden: share.HiddenByOwner,
            Properties: share.Properties,
        },
        function (response) {
            let json_response = JSON.parse(response);
            if (json_response["Status"] !== "success") {
                callback(json_response["Status"] || "Unknown error");
            } else {
                callback(null);
            }
        },
        null,
        function (error) {
            callback(error);
        }
    );
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Share} share
 * @param {function(?string):void} callback
 */
export function add_share_by_map(
    user,
    password,
    share,
    callback,
) {
    call_sharing_api(
        user,
        password,
        "map/create",
        {
            PathMapped: share.PathMapped,
            Permissions: share.Permissions,
            Enabled: share.EnabledByOwner,
            Hidden: share.HiddenByOwner,
            Properties: share.Properties,
            User: share.User,
            PathOrToken: share.PathOrToken,
        },
        function (response) {
            let json_response = JSON.parse(response);
            if (json_response["Status"] !== "success") {
                callback(json_response["Status"] || "Unknown error");
            } else {
                callback(null);
            }
        },
        null,
        function (error) {
            callback(error);
        }
    );
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Share} share
 * @param {function(?string):void} callback
 */
export function delete_share_by_token(
    user,
    password,
    share,
    callback,
) {
    call_sharing_api(
        user,
        password,
        "token/delete",
        { PathOrToken: share.PathOrToken },
        function (response) {
            let json_response = JSON.parse(response);
            if (json_response["Status"] !== "success") {
                callback(json_response["Status"] || "Unknown error");
            } else {
                callback(null);
            }
        },
        null,
        function (error) {
            callback(error);
        }
    );
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Share} share
 * @param {function(?string):void} callback
 */
export function delete_share_by_map(
    user,
    password,
    share,
    callback,
) {
    call_sharing_api(
        user,
        password,
        "map/delete",
        { PathOrToken: share.PathOrToken },
        function (response) {
            let json_response = JSON.parse(response);
            if (json_response["Status"] !== "success") {
                callback(json_response["Status"] || "Unknown error");
            } else {
                callback(null);
            }
        },
        null,
        function (error) {
            callback(error);
        }
    );
}
/**
 * @param {string} user
 * @param {string} password
 * @param {Share} share
 * @param {function(?string):void} callback
 */
export function update_share_by_token(
    user,
    password,
    share,
    callback,
) {
    call_sharing_api(
        user,
        password,
        "token/update",
        {
            PathOrToken: share.PathOrToken,
            Permissions: share.Permissions,
            Enabled: share.EnabledByOwner,
            Hidden: share.HiddenByOwner,
            Properties: share.Properties,
        },
        function (response) {
            let json_response = JSON.parse(response);
            if (json_response["Status"] !== "success") {
                callback(json_response["Status"] || "Unknown error");
            } else {
                callback(null);
            }
        },
        null,
        function (error) {
            callback(error);
        }
    );
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Share} share
 * @param {function(?string):void} callback
 */
export function update_share_by_map(
    user,
    password,
    share,
    callback,
) {
    call_sharing_api(
        user,
        password,
        "map/update",
        {
            PathOrToken: share.PathOrToken,
            PathMapped: share.PathMapped,
            User: share.User,
            Permissions: share.Permissions,
            Enabled: share.EnabledByOwner,
            Hidden: share.HiddenByOwner,
            Properties: share.Properties,
        },
        function (response) {
            let json_response = JSON.parse(response);
            if (json_response["Status"] !== "success") {
                callback(json_response["Status"] || "Unknown error");
            } else {
                callback(null);
            }
        },
        null,
        function (error) {
            callback(error);
        }
    );
}

/**
 * Update a shared map entry as the recipient user.
 * Only sends fields the non-owner user is allowed to change: PathOrToken, EnabledByUser, HiddenByUser.
 * @param {string} user
 * @param {string} password
 * @param {Share} share
 * @param {function(?string):void} callback
 */
export function update_incoming_share(
    user,
    password,
    share,
    callback,
) {
    call_sharing_api(
        user,
        password,
        "map/update",
        {
            PathOrToken: share.PathOrToken,
            Enabled: share.EnabledByUser,
            Hidden: share.HiddenByUser,
        },
        function (response) {
            let json_response = JSON.parse(response);
            if (json_response["Status"] !== "success") {
                callback(json_response["Status"] || "Unknown error");
            } else {
                callback(null);
            }
        },
        null,
        function (error) {
            callback(error);
        }
    );
}
