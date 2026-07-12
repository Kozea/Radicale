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
import { create_request, to_error_message } from "./common.js";

/**
 * @typedef {Object} SharingFeatures
 * @property {number} [ApiVersion]
 * @property {string} [Status]
 * @property {boolean} [FeatureEnabledCollectionByMap]
 * @property {boolean} [PermittedCreateCollectionByMap]
 * @property {boolean} [FeatureEnabledCollectionByToken]
 * @property {boolean} [PermittedCreateCollectionByToken]
 * @property {Array<string>} [SupportedConversions]
 */

/**
 * @typedef {Object} ServerFeatures
 * @property {SharingFeatures} [sharing]
 */

/**
 * @param {string} user
 * @param {?string} password
 * @param {string} path
 * @param {object} body
 * @param {(response: string) => void} on_success
 * @param {(() => void) | null} on_not_found
 * @param {((error: string) => void) | null} on_error
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
    let request = create_request(
        "POST",
        SERVER + ROOT_PATH + ".sharing/v1/" + path,
        user,
        password,
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
                on_error(to_error_message(request));
            } else {
                console.error(to_error_message(request));
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
 * @param {?string} password
 * @param {(features: import("../api/sharing.js").ServerFeatures, error: string | null) => void} callback
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
                if (e instanceof Error) {
                    callback({}, e.message);
                } else {
                    callback({}, e ? e.toString() : "Unknown error");
                }
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

/**
 * @typedef {Object} ShareData
 * @property {string} [ShareType]
 * @property {string} [PathOrToken]
 * @property {string} [PathMapped]
 * @property {string} [Owner]
 * @property {string} [User]
 * @property {string} [Permissions]
 * @property {?boolean} [EnabledByOwner]
 * @property {?boolean} [EnabledByUser]
 * @property {?boolean} [HiddenByOwner]
 * @property {?boolean} [HiddenByUser]
 * @property {number} [TimestampCreated]
 * @property {number} [TimestampUpdated]
 * @property {Object<String, String>} [Properties]
 * @property {string} [Conversion]
 * @property {Object<String, *>} [Actions]
 */

export class ConfigProperty {
    /**
     * @param {string} key
     * @param {string} type
     * @param {string} displayName
     */
    constructor(key, type, displayName) {
        /** @type {string} */ this.key = key;
        /** @type {string} */ this.type = type;
        /** @type {string} */ this.displayName = displayName;
    }
}

export const BDAY_CONFIG = Object.freeze([
    Object.freeze(new ConfigProperty("conversion_bday_summary_template", "str", "Summary template")),
    Object.freeze(new ConfigProperty("conversion_bday_description_template", "str", "Description template")),
    Object.freeze(new ConfigProperty("conversion_bday_alarm_trigger_template", "str", "Alarm trigger template")),
    Object.freeze(new ConfigProperty("conversion_bday_categories", "str", "Categories")),
    Object.freeze(new ConfigProperty("conversion_bday_age_max", "int", "Max age"))
]);

export class ShareConfig {
    /** @type {Record<string, any>} */
    _values = {};
    /**
     * @param {ShareConfig|Record<string, any>} [data]
     */
    constructor(data = {}) {
        let rawData = data;
        if (data instanceof ShareConfig) {
            rawData = data._values;
        }
        for (const [key, value] of Object.entries(rawData || {})) {
            const bdayProp = BDAY_CONFIG.find(c => c.key === key);
            if (bdayProp && bdayProp.type === "int" && value !== null && value !== undefined) {
                let parsed = parseInt(String(value), 10);
                this._values[key] = isNaN(parsed) ? value : parsed;
            } else {
                this._values[key] = value;
            }
        }
    }

    /**
     * @param {ConfigProperty} property
     * @returns {any}
     */
    get(property) {
        let val = this._values[property.key] ?? null;
        return val === "#DEL#" ? null : val;
    }

    /**
     * @param {ConfigProperty} property
     * @param {any} val
     */
    set(property, val) {
        if (val === undefined || val === null || val === "") {
            this._values[property.key] = null;
        } else if (property.type === "int") {
            let parsed = parseInt(String(val), 10);
            this._values[property.key] = isNaN(parsed) ? val : parsed;
        } else {
            this._values[property.key] = val;
        }
    }

    /**
     * @param {ConfigProperty|string} property
     */
    delete(property) {
        const key = typeof property === "string" ? property : property.key;
        this._values[key] = "#DEL#";
    }

    /**
     * @param {ConfigProperty} property
     * @returns {boolean}
     */
    isDeleted(property) {
        return this._values[property.key] === "#DEL#";
    }

    /**
     * @returns {Record<string, any>}
     */
    toJSON() {
        /** @type {Record<string, any>} */
        let obj = {};
        for (const [key, value] of Object.entries(this._values)) {
            if (value !== null) {
                obj[key] = value;
            }
        }
        return obj;
    }
}

export class ShareActions {
    /**
     * @param {Record<string, any>} [data]
     */
    constructor(data = {}) {
        /** @type {ShareConfig} */
        this._config = new ShareConfig(data.config || {});
        for (const [key, value] of Object.entries(data)) {
            if (key !== "config") {
                (/** @type {any} */ (this))[key] = value;
            }
        }
    }

    /**
     * @returns {ShareConfig}
     */
    get config() {
        return this._config;
    }

    /**
     * @param {ShareConfig|Record<string, any>} value
     */
    set config(value) {
        if (value instanceof ShareConfig) {
            this._config = value;
        } else {
            this._config = new ShareConfig(value || {});
        }
    }

    /**
     * @returns {Record<string, any>|undefined}
     */
    toJSON() {
        /** @type {Record<string, any>} */
        let obj = {};
        for (const [key, value] of Object.entries(this)) {
            if (key === "_config" && value instanceof ShareConfig) {
                let configJSON = value.toJSON();
                if (Object.keys(configJSON).length > 0) {
                    obj.config = configJSON;
                }
            } else if (value !== null && value !== undefined) {
                obj[key] = value;
            }
        }
        return Object.keys(obj).length > 0 ? obj : undefined;
    }
}

export class Share {
    /**
     * @param {ShareData} [data]
     */
    constructor(data = {}) {
        /** @type {string} */ this.ShareType = data.ShareType || "";
        /** @type {string} */ this.PathOrToken = data.PathOrToken || "";
        /** @type {string} */ this.PathMapped = data.PathMapped || "";
        /** @type {string} */ this.Owner = data.Owner || "";
        /** @type {string} */ this.User = data.User || "";
        /** @type {string} */ this.Permissions = data.Permissions || "r";
        /** @type {?boolean} */ this.EnabledByOwner = data.EnabledByOwner ?? null;
        /** @type {?boolean} */ this.EnabledByUser = data.EnabledByUser ?? null;
        /** @type {?boolean} */ this.HiddenByOwner = data.HiddenByOwner ?? null;
        /** @type {?boolean} */ this.HiddenByUser = data.HiddenByUser ?? null;
        /** @type {number} */ this.TimestampCreated = data.TimestampCreated || 0;
        /** @type {number} */ this.TimestampUpdated = data.TimestampUpdated || 0;
        /** @type {Object<String, String>} */ this.Properties = data.Properties || {};
        /** @type {string} */ this.Conversion = data.Conversion || "";
        /** @type {ShareActions} */
        this._Actions = data.Actions instanceof ShareActions ? data.Actions : new ShareActions(data.Actions || {});
    }

    /**
     * @returns {ShareActions}
     */
    get Actions() {
        return this._Actions;
    }

    /**
     * @param {ShareActions|Record<string, any>} value
     */
    set Actions(value) {
        if (value instanceof ShareActions) {
            this._Actions = value;
        } else {
            this._Actions = new ShareActions(value || {});
        }
    }

    /**
     * @returns {ShareConfig}
     */
    get config() {
        return this.Actions.config;
    }

    /**
     * @param {ShareConfig|Record<string, any>} value
     */
    set config(value) {
        this.Actions.config = value;
    }
}

/**
 * @param {string} user
 * @param {?string} password
 * @param {?import("../models/collection.js").Collection} collection
 * @param {(shares: Array<Share>, error: string | null) => void} callback
 */
export function reload_sharing_list(user, password, collection, callback) {
    let body = collection ? { PathMapped: decodeURIComponent(collection.href) } : {};
    return call_sharing_api(
        user,
        password,
        "all/list",
        body,
        function (response) {
            let parsed = JSON.parse(response);
            let shares = (parsed["Content"] || []).map((/** @type {ShareData} */ data) => new Share(data));
            callback(shares, null);
        },
        function () {
            // sharing is disabled on the server
            callback([], null);
        },
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
 * @param {"DISPLAYNAME" | "DESCRIPTION" | "COLOR"} property Property name
 * @returns {string | null} Internal property key or null if not supported
 */
export function get_property_key(type, property) {
    if (property === "DISPLAYNAME") {
        return "D:displayname";
    }
    if (type === CollectionType.ADDRESSBOOK) {
        return OVERLAY_PROPERTIES.ADDRESSBOOK[property];
    } else if (CollectionType.is_subset(CollectionType.CALENDAR, type)) {
        return OVERLAY_PROPERTIES.CALENDAR[property];
    }
    return null;
}

/**
 * @param {string} user
 * @param {?string} password
 * @param {Share} share
 * @param {(error: string | null) => void} callback
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
            PathMapped: decodeURIComponent(share.PathMapped),
            Permissions: share.Permissions,
            Enabled: share.EnabledByOwner,
            Hidden: share.HiddenByOwner,
            Properties: share.Properties,
            Conversion: share.Conversion,
            Actions: share.Actions,
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
 * @param {?string} password
 * @param {Share} share
 * @param {(error: string | null) => void} callback
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
            PathMapped: decodeURIComponent(share.PathMapped),
            Permissions: share.Permissions,
            Enabled: share.EnabledByOwner,
            Hidden: share.HiddenByOwner,
            Properties: share.Properties,
            User: share.User,
            PathOrToken: decodeURIComponent(share.PathOrToken),
            Conversion: share.Conversion,
            Actions: share.Actions,
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
 * @param {?string} password
 * @param {Share} share
 * @param {(error: string | null) => void} callback
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
        { PathOrToken: decodeURIComponent(share.PathOrToken) },
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
 * @param {?string} password
 * @param {Share} share
 * @param {(error: string | null) => void} callback
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
        { PathOrToken: decodeURIComponent(share.PathOrToken) },
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
 * @param {?string} password
 * @param {Share} share
 * @param {(error: string | null) => void} callback
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
            PathOrToken: decodeURIComponent(share.PathOrToken),
            Permissions: share.Permissions,
            Enabled: share.EnabledByOwner,
            Hidden: share.HiddenByOwner,
            Properties: share.Properties,
            Conversion: share.Conversion,
            Actions: share.Actions,
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
 * @param {?string} password
 * @param {Share} share
 * @param {(error: string | null) => void} callback
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
            PathOrToken: decodeURIComponent(share.PathOrToken),
            PathMapped: decodeURIComponent(share.PathMapped),
            User: share.User,
            Permissions: share.Permissions,
            Enabled: share.EnabledByOwner,
            Hidden: share.HiddenByOwner,
            Properties: share.Properties,
            Conversion: share.Conversion,
            Actions: share.Actions,
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
 * @param {?string} password
 * @param {Share} share
 * @param {(error: string | null) => void} callback
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
        share.ShareType + "/update",
        {
            PathOrToken: decodeURIComponent(share.PathOrToken),
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

