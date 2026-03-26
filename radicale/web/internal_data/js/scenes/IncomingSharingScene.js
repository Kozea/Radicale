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

/**
 * @implements {Scene}
 */
export class IncomingSharingScene {
    /**
     * @param {string} user
     * @param {?string} password
     */
    constructor(user, password) {
        /** @type {HTMLElement} */ let html_scene = get_element_by_id("incomingsharingscene");
        /** @type {HTMLElement} */ let cancel_btn = get_element(html_scene, "[data-name=cancel]");
        /** @type {HTMLElement} */ let error_element = get_element(html_scene, "[data-name=error]");
        /** @type {HTMLElement} */ let tbody = get_element(html_scene, "tbody[data-name=incomingsharesbody]");
        /** @type {HTMLElement} */ let template = get_element(tbody, "[data-name=incomingsharerowtemplate]");
        /** @type {HTMLElement} */ let table = get_element(html_scene, "table");
        /** @type {HTMLElement} */ let noshares_message = get_element(html_scene, "[data-name=nosharesmessage]");

        let error_handler = new ErrorHandler(error_element);

        /** @type {Array<HTMLElement>} */ let nodes = [];

        function on_cancel() {
            pop_scene();
        }

        /**
         * @param {import("../api/sharing.js").Share} share
         * @param {HTMLElement} node
         */
        function toggle_share(share, node) {
            let enabled_cb = /** @type {HTMLInputElement} */ (node.querySelector("[data-name=enabled]"));
            let shown_cb = /** @type {HTMLInputElement} */ (node.querySelector("[data-name=shown]"));

            // disable checkboxes while updating
            enabled_cb.disabled = true;
            shown_cb.disabled = true;

            let old_enabled = share.EnabledByUser || false;
            let old_hidden = share.HiddenByUser || false;

            share.EnabledByUser = enabled_cb.checked;
            share.HiddenByUser = !shown_cb.checked;
            error_handler.clearError();

            update_incoming_share(user, password, share, function (error) {
                enabled_cb.disabled = false;
                shown_cb.disabled = !share.EnabledByUser;

                if (error) {
                    error_handler.setError(error);
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
        function render_shares(shares) {
            // clear old nodes
            nodes.forEach(function (node) {
                if (node.parentNode) {
                    node.parentNode.removeChild(node);
                }
            });
            nodes = [];

            let prefix = "/" + user + "/";
            let filtered_shares = shares.filter(
                share => (share.ShareType === "map")
                    && share.PathOrToken.startsWith(prefix));

            if (filtered_shares.length === 0) {
                table.classList.add("hidden");
                noshares_message.classList.remove("hidden");
            } else {
                table.classList.remove("hidden");
                noshares_message.classList.add("hidden");
            }

            filtered_shares.forEach(function (share) {
                let node = /** @type {HTMLElement} */(template.cloneNode(true));
                node.classList.remove("hidden");

                let pathortoken = /** @type {HTMLInputElement} */ (get_element(node, "[data-name=pathortoken]"));
                let owner_td = get_element(node, "[data-name=owner]");
                let permissions_td = /** @type {HTMLElement} */ (get_element(node, "[data-name=permissions]"));
                let enabled_cb = /** @type {HTMLInputElement} */ (get_element(node, "[data-name=enabled]"));
                let shown_cb = /** @type {HTMLInputElement} */ (get_element(node, "[data-name=shown]"));

                let displayPath = share.PathOrToken.substring(prefix.length);
                if (displayPath.endsWith("/")) {
                    displayPath = displayPath.substring(0, displayPath.length - 1);
                }

                pathortoken.value = displayPath;
                owner_td.textContent = share.Owner;
                displayPermissionsOrConversion(share.Conversion, share.Permissions, permissions_td);

                let enabled = share.EnabledByUser !== null ? share.EnabledByUser : true;
                let shown = share.HiddenByUser !== null ? !share.HiddenByUser : true;

                enabled_cb.checked = enabled;
                shown_cb.checked = shown;
                shown_cb.disabled = !enabled;

                enabled_cb.onchange = function () { toggle_share(share, node); };
                shown_cb.onchange = function () { toggle_share(share, node); };

                nodes.push(node);
                tbody.appendChild(node);
            });
        }

        this.show = function () {
            html_scene.classList.remove("hidden");
            cancel_btn.onclick = on_cancel;
            error_handler.clearError();
            collectionsCache.getIncomingShares(user, password, error_handler.setError, render_shares);
        };

        this.hide = function () {
            html_scene.classList.add("hidden");
            cancel_btn.onclick = null;
            error_handler.clearError();
        };

        this.is_transient = function () { return false; };
        this.release = function () {
            error_handler.clearError();
            nodes.forEach(function (node) {
                if (node.parentNode) {
                    node.parentNode.removeChild(node);
                }
            });
            nodes = [];
        };
    }
}
