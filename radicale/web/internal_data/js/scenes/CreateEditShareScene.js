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

import { Share, add_share_by_map, add_share_by_token, get_property_key, update_share_by_map, update_share_by_token } from "../api/sharing.js";
import { CollectionType } from "../models/collection.js";
import { ErrorHandler } from "../utils/error.js";
import { FormValidator, validate_href, validate_non_empty } from "../utils/form_validator.js";
import { onCleanHREFinput, random_uuid } from "../utils/misc.js";
import { Scene, pop_scene, scene_stack } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class CreateEditShareScene {
    /**
     * @param {string} user
     * @param {string} password
     * @param {import("../models/collection.js").Collection} collection
     * @param {string} shareType
     * @param {function():void} onclose
     * @param {Share} [share] If provided, the scene will be in edit mode.
     */
    constructor(user, password, collection, shareType, onclose, share) {
        let edit = !!share;
        let pathMapped = collection.href;
        /** @type {HTMLElement} */ let html_scene = document.getElementById("newshare");
        /** @type {HTMLFormElement} */ let form = html_scene.querySelector("form");
        /** @type {HTMLElement} */ let sharemapfields = html_scene.querySelector("[data-name=sharemapfields]");
        /** @type {HTMLInputElement} */ let shareuser_input = html_scene.querySelector("[data-name=shareuser]");
        /** @type {HTMLInputElement} */ let sharehref_input = html_scene.querySelector("[data-name=sharehref]");
        /** @type {HTMLInputElement} */ let enabled_checkbox = html_scene.querySelector("[data-name=enabled]");
        /** @type {HTMLInputElement} */ let hidden_checkbox = html_scene.querySelector("[data-name=hidden]");
        let permissions_ro_radio = /** @type {HTMLInputElement} */ (document.getElementById("newshare_attr_permissions_ro"));
        let permissions_rw_radio = /** @type {HTMLInputElement} */ (document.getElementById("newshare_attr_permissions_rw"));

        /** @type {HTMLElement} */ let properties_fieldset = html_scene.querySelector("[data-name=properties_override]");
        /** @type {HTMLInputElement} */ let description_override_enabled = html_scene.querySelector("[data-name=description_override_enabled]");
        /** @type {HTMLInputElement} */ let description_override_input = html_scene.querySelector("[data-name=description_override]");
        /** @type {HTMLInputElement} */ let color_override_enabled = html_scene.querySelector("[data-name=color_override_enabled]");
        /** @type {HTMLInputElement} */ let color_override_input = html_scene.querySelector("[data-name=color_override]");

        /** @type {HTMLElement} */ let error_form = html_scene.querySelector("[data-name=error]");
        /** @type {HTMLElement} */ let submit_btn = html_scene.querySelector("[data-name=submit]");
        /** @type {HTMLElement} */ let cancel_btn = html_scene.querySelector("[data-name=cancel]");

        let errorHandler = new ErrorHandler(error_form);
        let map_validator = new FormValidator(errorHandler);

        map_validator.addValidator(shareuser_input, validate_non_empty(shareuser_input, "Share User"));
        map_validator.addValidator(sharehref_input, validate_href(sharehref_input, "Share Href"));

        sharehref_input.addEventListener("input", onCleanHREFinput);

        description_override_enabled.onchange = function () {
            description_override_input.disabled = !description_override_enabled.checked;
        };
        color_override_enabled.onchange = function () {
            color_override_input.disabled = !color_override_enabled.checked;
        };

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
                if (shareType === "map") {
                    if (!map_validator.validate()) {
                        return false;
                    }
                }
                let enabled = enabled_checkbox.checked;
                let hidden = hidden_checkbox.checked;
                let permissions = permissions_rw_radio.checked ? "rw" : "r";

                let properties = {};
                if (description_override_enabled.checked) {
                    let key = get_property_key(collection.type, "DESCRIPTION");
                    if (key) properties[key] = description_override_input.value;
                }
                if (color_override_enabled.checked) {
                    let key = get_property_key(collection.type, "COLOR");
                    if (key) properties[key] = color_override_input.value + (color_override_input.value ? "ff" : "");
                }

                let callback = function (/** @type {string} */ error) {
                    if (scene_index === null) {
                        return;
                    }
                    if (error) {
                        errorHandler.setError(error);
                    } else {
                        pop_scene(scene_index - 1);
                        if (onclose) onclose();
                    }
                };

                let new_share = new Share({
                    ShareType: shareType,
                    PathMapped: pathMapped,
                    Permissions: permissions,
                    Enabled: enabled,
                    Hidden: hidden,
                    Properties: properties,
                    User: edit ? share.User : shareuser_input.value,
                    PathOrToken: edit ? share.PathOrToken : (shareType === "map" ? "/" + shareuser_input.value + "/" + sharehref_input.value : ""),
                });

                if (edit) {
                    if (shareType === "map") {
                        update_share_by_map(user, password, new_share, callback);
                    } else {
                        update_share_by_token(user, password, new_share, callback);
                    }
                } else {
                    if (shareType === "map") {
                        add_share_by_map(user, password, new_share, callback);
                    } else {
                        add_share_by_token(user, password, new_share, callback);
                    }
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

            html_scene.querySelector("h1").textContent = edit ? "Edit Share" : "New Share";
            submit_btn.textContent = edit ? "Save" : "Create";

            shareuser_input.value = edit ? share.User : "";
            shareuser_input.disabled = edit;
            enabled_checkbox.checked = edit ? share.Enabled : true;
            hidden_checkbox.checked = edit ? share.Hidden : false;
            permissions_ro_radio.checked = edit ? share.Permissions.toLowerCase() === "r" : true;
            permissions_rw_radio.checked = edit ? share.Permissions.toLowerCase() === "rw" : false;

            let description = collection.description || "";
            let color = collection.color || "#ffffff";
            let description_override_enabled_value = false;
            let color_override_enabled_value = false;

            if (edit && share.Properties) {
                let description_key = get_property_key(collection.type, "DESCRIPTION");
                if (description_key && share.Properties[description_key]) {
                    description = share.Properties[description_key];
                    description_override_enabled_value = true;
                }
                let color_key = get_property_key(collection.type, "COLOR");
                if (color_key && share.Properties[color_key]) {
                    color = share.Properties[color_key];
                    if (color.length === 9 && color.endsWith("ff")) {
                        color = color.substring(0, 7);
                    }
                    color_override_enabled_value = true;
                }
            }

            description_override_enabled.checked = description_override_enabled_value;
            description_override_input.value = description;
            description_override_input.disabled = !description_override_enabled_value;

            color_override_enabled.checked = color_override_enabled_value;
            color_override_input.value = color;
            color_override_input.disabled = !color_override_enabled_value;

            let is_calendar = CollectionType.is_subset(CollectionType.CALENDAR, collection.type);
            let is_addressbook = collection.type === CollectionType.ADDRESSBOOK;
            if (is_calendar || is_addressbook) {
                properties_fieldset.classList.remove("hidden");
            } else {
                properties_fieldset.classList.add("hidden");
            }

            if (shareType === "map") {
                if (edit) {
                    sharehref_input.value = share.PathOrToken.split("/").pop() || "";
                } else {
                    sharehref_input.value = random_uuid();
                }
                sharehref_input.disabled = edit;
                sharemapfields.classList.remove("hidden");
                map_validator.validate();
            } else {
                sharehref_input.value = "";
                sharemapfields.classList.add("hidden");
                errorHandler.clearError();
            }
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
