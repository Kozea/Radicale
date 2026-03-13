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

import { Share, reload_sharing_list, update_incoming_share } from "../api/sharing.js";
import { ErrorHandler } from "../utils/error.js";
import { displayPermissions } from "../utils/permissions.js";
import { LoadingScene } from "./LoadingScene.js";
import { Scene, pop_scene, push_scene, scene_stack } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class IncomingSharingScene {
    /**
     * @param {string} user
     * @param {string} password
     */
    constructor(user, password) {
        /** @type {HTMLElement} */ let html_scene = document.getElementById("incomingsharingscene");
        /** @type {HTMLElement} */ let cancel_btn = html_scene.querySelector("[data-name=cancel]");
        /** @type {HTMLElement} */ let error_element = html_scene.querySelector("[data-name=error]");
        /** @type {HTMLElement} */ let tbody = html_scene.querySelector("tbody[data-name=incomingsharesbody]");
        /** @type {HTMLElement} */ let template = tbody.querySelector("[data-name=incomingsharerowtemplate]");

        let error_handler = new ErrorHandler(error_element);

        /** @type {?number} */ let scene_index = null;
        /** @type {Array<HTMLElement>} */ let nodes = [];
        /** @type {?Array<Object>} */ let shares_cache = null;

        function on_cancel() {
            pop_scene(scene_index - 1);
        }

        /**
         * @param {Share} share
         * @param {HTMLElement} node
         */
        function toggle_share(share, node) {
            let enabled_cb = /** @type {HTMLInputElement} */ (node.querySelector("[data-name=enabled]"));
            let hidden_cb = /** @type {HTMLInputElement} */ (node.querySelector("[data-name=hidden]"));

            // disable checkboxes while updating
            enabled_cb.disabled = true;
            hidden_cb.disabled = true;

            let old_enabled = share.EnabledByUser;
            let old_hidden = share.HiddenByUser;

            share.EnabledByUser = enabled_cb.checked;
            share.HiddenByUser = hidden_cb.checked;
            error_handler.clearError();

            update_incoming_share(user, password, share, function (error) {
                enabled_cb.disabled = false;
                hidden_cb.disabled = false;

                if (error) {
                    error_handler.setError(error);
                    enabled_cb.checked = old_enabled;
                    hidden_cb.checked = old_hidden;
                }
            });
        }

        /**
         * @param {Share[]} shares
         */
        function render_shares(shares) {
            // clear old nodes
            nodes.forEach(function (node) {
                node.parentNode.removeChild(node);
            });
            nodes = [];

            let prefix = "/" + user + "/";
            let filtered_shares = shares.filter(share => share.ShareType === "map" && share.PathOrToken.startsWith(prefix));

            filtered_shares.forEach(function (share) {
                let node = /** @type {HTMLElement} */(template.cloneNode(true));
                node.classList.remove("hidden");

                let pathortoken_td = node.querySelector("[data-name=pathortoken]");
                let owner_td = node.querySelector("[data-name=owner]");
                let permissions_td = /** @type {HTMLElement} */ node.querySelector("[data-name=permissions]");
                let enabled_cb = /** @type {HTMLInputElement} */ (node.querySelector("[data-name=enabled]"));
                let hidden_cb = /** @type {HTMLInputElement} */ (node.querySelector("[data-name=hidden]"));

                let displayPath = share.PathOrToken.substring(prefix.length);
                if (displayPath.endsWith("/")) {
                    displayPath = displayPath.substring(0, displayPath.length - 1);
                }

                pathortoken_td.textContent = displayPath;
                owner_td.textContent = share.Owner;
                displayPermissions(share.Permissions, permissions_td);

                enabled_cb.checked = share.EnabledByUser;
                hidden_cb.checked = share.HiddenByUser;

                enabled_cb.onchange = function () { toggle_share(share, node); };
                hidden_cb.onchange = function () { toggle_share(share, node); };

                nodes.push(node);
                tbody.appendChild(node);
            });
        }

        function update() {
            let loading_scene = new LoadingScene();
            push_scene(loading_scene, false);

            error_handler.clearError();

            reload_sharing_list(user, password, null, function (shares, error) {
                if (scene_index === null) {
                    return;
                }
                if (error) {
                    error_handler.setError(error);
                    pop_scene(scene_index - 1);
                } else {
                    shares_cache = shares;
                    pop_scene(scene_index);
                }
            });
        }

        this.show = function () {
            scene_index = scene_stack.length - 1;
            html_scene.classList.remove("hidden");
            cancel_btn.onclick = on_cancel;
            if (shares_cache === null) {
                update();
            } else {
                render_shares(shares_cache);
            }
        };

        this.hide = function () {
            html_scene.classList.add("hidden");
            cancel_btn.onclick = null;
            error_handler.clearError();

            nodes.forEach(function (node) {
                node.parentNode.removeChild(node);
            });
            nodes = [];
            shares_cache = null;
        };

        this.release = function () {
            scene_index = null;
            error_handler.clearError();
            shares_cache = null;
        };
    }
}
