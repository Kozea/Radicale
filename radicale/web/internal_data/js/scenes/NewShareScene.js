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

import { add_share_by_map, add_share_by_token } from "../api/api.js";
import { onCleanHREFinput } from "../utils/misc.js";
import { Scene, pop_scene, scene_stack } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class NewShareScene {
    /**
     * @param {string} user
     * @param {string} password
     * @param {string} pathMapped
     * @param {string} shareType
     * @param {function():void} onclose
     */
    constructor(user, password, pathMapped, shareType, onclose) {
        /** @type {HTMLElement} */ let html_scene = document.getElementById("newshare");
        /** @type {HTMLFormElement} */ let form = html_scene.querySelector("form");
        /** @type {HTMLElement} */ let sharemapfields = html_scene.querySelector("[data-name=sharemapfields]");
        /** @type {HTMLInputElement} */ let shareuser_input = html_scene.querySelector("[data-name=shareuser]");
        /** @type {HTMLInputElement} */ let sharehref_input = html_scene.querySelector("[data-name=sharehref]");
        /** @type {HTMLInputElement} */ let enabled_checkbox = html_scene.querySelector("[data-name=enabled]");
        /** @type {HTMLInputElement} */ let hidden_checkbox = html_scene.querySelector("[data-name=hidden]");
        let permissions_ro_radio = /** @type {HTMLInputElement} */ (document.getElementById("newshare_attr_permissions_ro"));
        let permissions_rw_radio = /** @type {HTMLInputElement} */ (document.getElementById("newshare_attr_permissions_rw"));
        /** @type {HTMLInputElement} */ let properties_input = html_scene.querySelector("[data-name=properties]");
        /** @type {HTMLElement} */ let cancel_btn = html_scene.querySelector("[data-name=cancel]");

        sharehref_input.addEventListener("input", onCleanHREFinput);

        /** @type {?number} */ let scene_index = null;

        function oncancel() {
            try {
                if (scene_index !== null) {
                    pop_scene(scene_index - 1);
                }
                if (onclose) onclose();
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        function onsubmit() {
            try {
                let enabled = enabled_checkbox.checked;
                let hidden = hidden_checkbox.checked;
                let permissions = permissions_rw_radio.checked ? "rw" : "r";
                let properties = properties_input.value;

                let callback = function () {
                    if (scene_index !== null) {
                        pop_scene(scene_index - 1);
                    }
                    if (onclose) onclose();
                };

                if (shareType === "map") {
                    let share_user = shareuser_input.value;
                    let href = sharehref_input.value;
                    add_share_by_map(user, password, pathMapped, permissions, enabled, hidden, properties, share_user, href, callback);
                } else {
                    add_share_by_token(user, password, pathMapped, permissions, enabled, hidden, properties, callback);
                }
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        this.show = function () {
            this.release();
            scene_index = scene_stack.length - 1;
            html_scene.classList.remove("hidden");
            cancel_btn.onclick = oncancel;
            form.onsubmit = onsubmit;

            if (shareType === "map") {
                sharemapfields.classList.remove("hidden");
            } else {
                sharemapfields.classList.add("hidden");
            }

            shareuser_input.value = "";
            sharehref_input.value = "";
            enabled_checkbox.checked = true;
            hidden_checkbox.checked = false;
            permissions_ro_radio.checked = true;
            permissions_rw_radio.checked = false;
            properties_input.value = "";
        };

        this.hide = function () {
            html_scene.classList.add("hidden");
            cancel_btn.onclick = null;
            form.onsubmit = null;
        };

        this.release = function () {
            scene_index = null;
        };
    }
}
