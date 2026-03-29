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

import { update_incoming_share } from "../api/sharing.js";
import { collectionsCache } from "../utils/collections_cache.js";
import { ErrorHandler } from "../utils/error.js";
import { get_element, get_element_by_id } from "../utils/misc.js";
import { displayPermissionsOrConversion } from "../utils/permissions.js";
import { Scene, pop_scene } from "./scene_manager.js";
import { UrlTextHandler } from "../utils/url_text.js";

/**
 * @implements {Scene}
 */
export class IncomingSharingScene {
    /**
     * @param {string} user
     * @param {?string} password
     */
    constructor(user, password) {
        this._user = user;
        this._password = password;

        this._html_scene = get_element_by_id("incomingsharingscene");
        this._cancel_btn = get_element(this._html_scene, "[data-name=cancel]");
        this._error_element = get_element(this._html_scene, "[data-name=error]");
        this._tbody = get_element(this._html_scene, "tbody[data-name=incomingsharesbody]");
        this._template = get_element(this._tbody, "[data-name=incomingsharerowtemplate]");
        this._table = get_element(this._html_scene, "table");
        this._noshares_message = get_element(this._html_scene, "[data-name=nosharesmessage]");

        this._error_handler = new ErrorHandler(this._error_element);

        /** @type {Array<HTMLElement>} */ this._nodes = [];
    }

    /**
     * @param {import("../api/sharing.js").Share} share
     * @param {HTMLElement} node
     */
    _toggle_share(share, node) {
        let enabled_cb = /** @type {HTMLInputElement} */ (node.querySelector("[data-name=enabled]"));
        let shown_cb = /** @type {HTMLInputElement} */ (node.querySelector("[data-name=shown]"));

        enabled_cb.disabled = true;
        shown_cb.disabled = true;

        let old_enabled = share.EnabledByUser || false;
        let old_hidden = share.HiddenByUser || false;

        share.EnabledByUser = enabled_cb.checked;
        share.HiddenByUser = !shown_cb.checked;
        this._error_handler.clearError();

        update_incoming_share(this._user, this._password, share, (error) => {
            enabled_cb.disabled = false;
            shown_cb.disabled = !share.EnabledByUser;

            if (error) {
                this._error_handler.setError(error);
                enabled_cb.checked = old_enabled;
                shown_cb.checked = !old_hidden;
                shown_cb.disabled = !old_enabled;
            } else {
                collectionsCache.invalidate();
            }
        });
    }

    /**
     * @param {import("../api/sharing.js").Share[]} shares
     */
    _render_shares(shares) {
        // clear old nodes
        this._nodes.forEach(function (node) {
            if (node.parentNode) {
                node.parentNode.removeChild(node);
            }
        });
        this._nodes = [];

        let prefix = "/" + this._user + "/";
        let filtered_shares = shares.filter(
            share => (share.ShareType === "map")
                && share.PathOrToken.startsWith(prefix));

        if (filtered_shares.length === 0) {
            this._table.classList.add("hidden");
            this._noshares_message.classList.remove("hidden");
        } else {
            this._table.classList.remove("hidden");
            this._noshares_message.classList.add("hidden");
        }

        filtered_shares.forEach((share) => {
            let node = /** @type {HTMLElement} */(this._template.cloneNode(true));
            node.classList.remove("hidden");

            let pathortoken = /** @type {HTMLInputElement} */ (get_element(node, "[data-name=pathortoken]"));
            let owner_td = get_element(node, "[data-name=owner]");
            let permissions_td = /** @type {HTMLElement} */ (get_element(node, "[data-name=permissions]"));
            let enabled_cb = /** @type {HTMLInputElement} */ (get_element(node, "[data-name=enabled]"));
            let shown_cb = /** @type {HTMLInputElement} */ (get_element(node, "[data-name=shown]"));
            let copy_btn = /** @type {HTMLButtonElement} */ (get_element(node, "[data-name=copy-url]"));

            new UrlTextHandler(pathortoken, copy_btn).setHref(share.PathOrToken);
            owner_td.textContent = share.Owner;
            displayPermissionsOrConversion(share.Conversion, share.Permissions, permissions_td);

            let enabled = share.EnabledByUser !== null ? share.EnabledByUser : true;
            let shown = share.HiddenByUser !== null ? !share.HiddenByUser : true;

            enabled_cb.checked = enabled;
            enabled_cb.setAttribute("title", "Enabled");
            shown_cb.checked = shown;
            shown_cb.setAttribute("title", "Shown");
            shown_cb.disabled = !enabled;

            enabled_cb.onchange = () => { this._toggle_share(share, node); };
            shown_cb.onchange = () => { this._toggle_share(share, node); };

            this._nodes.push(node);
            this._tbody.appendChild(node);
        });
    }

    show() {
        this._html_scene.classList.remove("hidden");
        this._cancel_btn.onclick = () => pop_scene();
        this._error_handler.clearError();
        collectionsCache.getIncomingShares(this._user, this._password, this._error_handler.setError, (shares) => this._render_shares(shares));
    }

    hide() {
        this._html_scene.classList.add("hidden");
        this._cancel_btn.onclick = null;
        this._error_handler.clearError();
    }

    is_transient() { return false; }

    release() {
        this._error_handler.clearError();
        this._nodes.forEach(function (node) {
            if (node.parentNode) {
                node.parentNode.removeChild(node);
            }
        });
        this._nodes = [];
    }
}
