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

import { get_collections } from "../api/api.js";
import { discover_server_features, reload_sharing_list } from "../api/sharing.js";
import { LoadingScene } from "../scenes/LoadingScene.js";
import { is_current_scene, pop_scene, push_scene } from "../scenes/scene_manager.js";

class CollectionsCache {
    constructor() {
        /** @type {?Array<import("../models/collection.js").Collection>} */ this.child_collections = null;
        /** @type {?Array<import("../api/sharing.js").Share>} */ this.incoming_shares = null;
        this.server_features = null;
        /** @type {?XMLHttpRequest} */ this.collections_req = null;
        /** @type {?XMLHttpRequest} */ this.shares_req = null;
        /** @type {?Array<{ onerror: function(string):void, displayData: function(Array<import("../api/sharing.js").Share>):void }>} */
        this._sharing_callbacks = null;
    }

    invalidate() {
        this.child_collections = null;
        this.incoming_shares = null;
        this.server_features = null;
        if (this.collections_req) {
            this.collections_req.abort();
            this.collections_req = null;
        }
        if (this.shares_req) {
            this.shares_req.abort();
            this.shares_req = null;
        }
        this._sharing_callbacks = null;
    }

    /**
     * @param {string} user
     * @param {?string} password
     * @param {import("../models/collection.js").Collection} principal_collection
     * @param {function(string):void} onerror
     * @param {function(Array<import("../models/collection.js").Collection>, Array<import("../api/sharing.js").Share>, boolean):void} displayData
     */
    getChildCollections(user, password, principal_collection, onerror, displayData) {
        if (this.child_collections !== null && this.incoming_shares !== null) {
            displayData(this.child_collections, this.incoming_shares, false);
            return;
        }

        let loading_scene = new LoadingScene();
        push_scene(loading_scene);

        /** @type {?Array<import("../models/collection.js").Collection>} */ let collections = null;
        /** @type {?Array<import("../api/sharing.js").Share>} */ let shares = null;
        /** @type {?string} */ let error = null;

        let check_if_completed = () => {
            if (!is_current_scene(loading_scene)) {
                return;
            }
            if (error) {
                onerror(error);
                this.child_collections = [];
                this.incoming_shares = [];
                pop_scene();
            } else if (collections !== null && shares !== null) {
                this.child_collections = collections;
                this.incoming_shares = shares;
                displayData(this.child_collections, this.incoming_shares, true);
                pop_scene();
            }
        };

        this.collections_req = get_collections(user, password, principal_collection, (c, e) => {
            this.collections_req = null;
            if (e) error = e;
            collections = c || [];
            check_if_completed();
        });

        this.shares_req = reload_sharing_list(user, password, null, (s, e) => {
            this.shares_req = null;
            if (e) error = e;
            shares = s || [];
            check_if_completed();
        });
    }

    /**
     * @param {string} user
     * @param {?string} password
     * @param {function(string):void} onerror
     * @param {function(Array<import("../api/sharing.js").Share>):void} displayData
     */
    getSharingList(user, password, onerror, displayData) {
        if (this.incoming_shares !== null) {
            displayData(this.incoming_shares);
            return;
        }

        if (!this._sharing_callbacks) {
            this._sharing_callbacks = [];
        }
        this._sharing_callbacks.push({ onerror, displayData });

        if (this.shares_req) {
            return;
        }

        this.shares_req = reload_sharing_list(user, password, null, (shares, error) => {
            this.shares_req = null;
            let callbacks = this._sharing_callbacks || [];
            this._sharing_callbacks = null;

            if (error) {
                callbacks.forEach(cb => cb.onerror(error));
            } else {
                this.incoming_shares = shares;
                callbacks.forEach(cb => cb.displayData(shares));
            }
        });
    }

    /**
     * @param {string} user
     * @param {?string} password
     * @param {function(string):void} onerror
     * @param {function(import("../api/sharing.js").ServerFeatures):void} displayData
     */
    getServerFeatures(user, password, onerror, displayData) {
        if (this.server_features !== null) {
            displayData(this.server_features);
            return;
        }

        discover_server_features(user, password, (features, error) => {
            if (error) {
                if (onerror) onerror(error);
            } else {
                this.server_features = features;
                displayData(this.server_features);
            }
        });
    }
}

export const collectionsCache = new CollectionsCache();
