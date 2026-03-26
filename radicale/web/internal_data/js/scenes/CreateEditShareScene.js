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
import { collectionsCache } from "../utils/collections_cache.js";
import { ErrorHandler } from "../utils/error.js";
import { FormValidator, validate_href, validate_non_empty, validate_not_empty_or_equals } from "../utils/form_validator.js";
import { get_element, get_element_by_id, onCleanHREFinput, random_uuid } from "../utils/misc.js";
import { Scene, is_current_scene, pop_scene } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class CreateEditShareScene {
    /**
     * @param {string} user
     * @param {?string} password
     * @param {import("../models/collection.js").Collection} collection
     * @param {string} shareType
     * @param {Share} [share] If provided, the scene will be in edit mode.
     */
    constructor(user, password, collection, shareType, share) {
        let self = this;
        let edit = !!share;
        let pathMapped = collection.href;
        /** @type {HTMLElement} */ let html_scene = get_element_by_id("newshare");
        /** @type {HTMLFormElement} */ let form = /** @type {HTMLFormElement} */ (get_element(html_scene, "form"));
        /** @type {HTMLElement} */ let sharemapfields = get_element(html_scene, "[data-name=sharemapfields]");
        /** @type {HTMLInputElement} */ let shareuser_input = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=shareuser]"));
        /** @type {HTMLInputElement} */ let sharehref_input = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=sharehref]"));
        /** @type {HTMLInputElement} */ let enabled_checkbox = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=enabled]"));
        /** @type {HTMLInputElement} */ let hidden_checkbox = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=hidden]"));
        let permissions_ro_radio = /** @type {HTMLInputElement} */ (get_element_by_id("newshare_attr_permissions_ro"));
        let permissions_rw_radio = /** @type {HTMLInputElement} */ (get_element_by_id("newshare_attr_permissions_rw"));
        /** @type {HTMLDetailsElement} */ let conversions_details = /** @type {HTMLDetailsElement} */ (get_element(html_scene, "[data-name=conversions]"));
        /** @type {HTMLElement} */ let conversions_container = get_element(html_scene, "[data-name=conversions_container]");

        /** @type {HTMLDetailsElement} */ let properties_fieldset = /** @type {HTMLDetailsElement} */ (get_element(html_scene, "[data-name=properties_override]"));
        /** @type {HTMLInputElement} */ let displayname_override_enabled = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=displayname_override_enabled]"));
        /** @type {HTMLInputElement} */ let displayname_override_input = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=displayname_override]"));
        /** @type {HTMLInputElement} */ let description_override_enabled = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=description_override_enabled]"));
        /** @type {HTMLInputElement} */ let description_override_input = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=description_override]"));
        /** @type {HTMLInputElement} */ let color_override_enabled = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=color_override_enabled]"));
        /** @type {HTMLInputElement} */ let color_override_input = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=color_override]"));

        /** @type {HTMLElement} */ let error_form = get_element(html_scene, "[data-name=error]");
        /** @type {HTMLElement} */ let submit_btn = get_element(html_scene, "[data-name=submit]");
        /** @type {HTMLElement} */ let cancel_btn = get_element(html_scene, "[data-name=cancel]");

        let errorHandler = new ErrorHandler(error_form);
        let map_validator = new FormValidator(errorHandler);

        map_validator.addValidator(shareuser_input, function () {
            let conversion = get_selected_conversion();
            if (conversion === "bday") {
                return validate_non_empty(shareuser_input, "Share User")();
            } else {
                return validate_not_empty_or_equals(shareuser_input, user, "Share User")();
            }
        });
        map_validator.addValidator(sharehref_input, validate_href(sharehref_input, "Share Href"));

        sharehref_input.addEventListener("input", onCleanHREFinput);

        displayname_override_enabled.onchange = function () {
            displayname_override_input.disabled = !displayname_override_enabled.checked;
        };
        description_override_enabled.onchange = function () {
            description_override_input.disabled = !description_override_enabled.checked;
        };
        color_override_enabled.onchange = function () {
            color_override_input.disabled = !color_override_enabled.checked;
        };
        function get_selected_conversion() {
            /** @type {HTMLInputElement | null} */
            let checked = conversions_container.querySelector("input[name=conversion]:checked");
            return checked ? checked.value : "none";
        }

        function on_conversion_change() {
            let conversion = get_selected_conversion();
            if (conversion === "bday") {
                permissions_ro_radio.checked = true;
                permissions_rw_radio.checked = false;
                permissions_ro_radio.disabled = true;
                permissions_rw_radio.disabled = true;
                enabled_checkbox.checked = true;
                hidden_checkbox.checked = false;
            } else {
                permissions_ro_radio.disabled = false;
                permissions_rw_radio.disabled = false;
            }
            if (shareType === "map") {
                map_validator.validate();
            }
        }

        function oncancel() {
            try {
                pop_scene();
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
                let conversion = get_selected_conversion();
                let is_birthday = conversion === "bday";
                let enabled_by_owner = is_birthday ? true : enabled_checkbox.checked;
                let hidden_by_owner = is_birthday ? false : hidden_checkbox.checked;
                let permissions = is_birthday ? "r" : (permissions_rw_radio.checked ? "rw" : "r");
                /** @type {string} */ let conversion_value = conversion;

                /** @type {Object<string, string>} */ let properties = {};
                if (displayname_override_enabled.checked) {
                    let key = get_property_key(collection.type, "DISPLAYNAME");
                    if (key) properties[key] = displayname_override_input.value;
                }
                if (description_override_enabled.checked) {
                    let key = get_property_key(collection.type, "DESCRIPTION");
                    if (key) properties[key] = description_override_input.value;
                }
                if (color_override_enabled.checked) {
                    let key = get_property_key(collection.type, "COLOR");
                    if (key) properties[key] = color_override_input.value + (color_override_input.value ? "ff" : "");
                }

                let callback = function (/** @type {?string} */ error) {
                    if (!is_current_scene(self)) {
                        return;
                    }
                    if (error) {
                        errorHandler.setError(error);
                    } else {
                        // On any share-to-self (currently only bday conversion), invalidate the
                        // collections cache so the virtual calendar appears immediately.
                        if (shareuser_input.value === user) {
                            collectionsCache.invalidate();
                        }
                        pop_scene();
                    }
                };

                let new_share = new Share({
                    ShareType: shareType,
                    PathMapped: pathMapped,
                    Permissions: permissions,
                    EnabledByOwner: enabled_by_owner,
                    EnabledByUser: (edit && share) ? share.EnabledByUser : null,
                    HiddenByOwner: hidden_by_owner,
                    HiddenByUser: (edit && share) ? share.HiddenByUser : null,
                    Properties: properties,
                    User: (edit && share) ? share.User : shareuser_input.value,
                    PathOrToken: (edit && share) ? share.PathOrToken : (shareType === "map" ? "/" + shareuser_input.value + "/" + sharehref_input.value + "/" : ""),
                    Conversion: conversion_value,
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
            html_scene.classList.remove("hidden");
            html_scene.querySelectorAll("details").forEach(function (details) {
                if (details.dataset.name !== "properties_override") {
                    details.open = true;
                } else {
                    details.open = false;
                }
            });
            cancel_btn.onclick = oncancel;
            form.onsubmit = onsubmit;

            /** @type {HTMLHeadingElement} */ let title = /** @type {HTMLHeadingElement} */ (get_element(html_scene, "h1"));
            title.textContent = edit ? "Edit Share" : "New Share";
            submit_btn.textContent = edit ? "Save" : "Create";

            shareuser_input.value = (edit && share) ? share.User : "";
            shareuser_input.disabled = edit;
            enabled_checkbox.checked = (edit && share && share.EnabledByOwner !== null) ? share.EnabledByOwner : true;
            hidden_checkbox.checked = (edit && share && share.HiddenByOwner !== null) ? share.HiddenByOwner : false;

            let initial_conversion = (edit && share && share.Conversion) ? share.Conversion : "none";

            collectionsCache.getServerFeatures(user, password, errorHandler.setError, (features) => {
                conversions_container.innerHTML = "";
                let supported = (features.sharing && features.sharing.SupportedConversions) || [];
                if (supported.length > 0) {
                    let options = ["none", ...supported.filter(opt => opt !== "none")];
                    options.forEach(opt => {
                        let id = "newshare_conv_" + opt;
                        let radio = document.createElement("input");
                        radio.type = "radio";
                        radio.name = "conversion";
                        radio.value = opt;
                        radio.id = id;
                        radio.checked = (opt === initial_conversion);
                        radio.onchange = on_conversion_change;

                        let label = document.createElement("label");
                        label.htmlFor = id;
                        if (opt === "bday") {
                            label.textContent = "Birthday";
                        } else {
                            label.textContent = opt.charAt(0).toUpperCase() + opt.slice(1);
                        }

                        conversions_container.appendChild(radio);
                        conversions_container.appendChild(label);
                    });

                    let is_addressbook = collection.type === CollectionType.ADDRESSBOOK;
                    if (is_addressbook) {
                        conversions_details.classList.remove("hidden");
                        conversions_details.open = true;
                    } else {
                        conversions_details.classList.add("hidden");
                    }
                } else {
                    conversions_details.classList.add("hidden");
                }
                on_conversion_change();
            });

            let displayname = collection.displayname || "";
            let description = collection.description || "";
            let color = collection.color || "#ffffff";
            let displayname_override_enabled_value = false;
            let description_override_enabled_value = false;
            let color_override_enabled_value = false;

            if (edit && share && share.Properties) {
                let displayname_key = get_property_key(collection.type, "DISPLAYNAME");
                if (displayname_key && share.Properties[displayname_key] !== undefined) {
                    displayname = share.Properties[displayname_key];
                    displayname_override_enabled_value = true;
                }
                let description_key = get_property_key(collection.type, "DESCRIPTION");
                if (description_key && share.Properties[description_key] !== undefined) {
                    description = share.Properties[description_key];
                    description_override_enabled_value = true;
                }
                let color_key = get_property_key(collection.type, "COLOR");
                if (color_key && share.Properties[color_key] !== undefined) {
                    color = share.Properties[color_key];
                    if (color.length === 9 && color.endsWith("ff")) {
                        color = color.substring(0, 7);
                    }
                    color_override_enabled_value = true;
                }
            }

            displayname_override_enabled.checked = displayname_override_enabled_value;
            displayname_override_input.value = displayname;
            displayname_override_input.disabled = !displayname_override_enabled_value;

            description_override_enabled.checked = description_override_enabled_value;
            description_override_input.value = description;
            description_override_input.disabled = !description_override_enabled_value;

            color_override_enabled.checked = color_override_enabled_value;
            color_override_input.value = color;
            color_override_input.disabled = !color_override_enabled_value;

            properties_fieldset.classList.remove("hidden");
            if (displayname_override_enabled_value || description_override_enabled_value || color_override_enabled_value) {
                properties_fieldset.open = true;
            }

            let displayname_key = get_property_key(collection.type, "DISPLAYNAME");
            if (!displayname_key) {
                if (displayname_override_enabled.parentElement) {
                    displayname_override_enabled.parentElement.classList.add("hidden");
                }
            } else {
                if (displayname_override_enabled.parentElement) {
                    displayname_override_enabled.parentElement.classList.remove("hidden");
                }
            }
            let description_key = get_property_key(collection.type, "DESCRIPTION");
            if (!description_key) {
                if (description_override_enabled.parentElement) {
                    description_override_enabled.parentElement.classList.add("hidden");
                }
            } else {
                if (description_override_enabled.parentElement) {
                    description_override_enabled.parentElement.classList.remove("hidden");
                }
            }

            let color_key = get_property_key(collection.type, "COLOR");
            if (!color_key) {
                if (color_override_enabled.parentElement) {
                    color_override_enabled.parentElement.classList.add("hidden");
                }
            } else {
                if (color_override_enabled.parentElement) {
                    color_override_enabled.parentElement.classList.remove("hidden");
                }
            }

            if (shareType === "map") {
                if (edit && share) {
                    sharehref_input.value = share.PathOrToken.split("/").filter(Boolean).pop() || "";
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
        };
    }
}
