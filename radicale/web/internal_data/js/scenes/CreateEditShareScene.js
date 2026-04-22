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
import { CollectionType, Permission } from "../models/collection.js";
import { extract_title } from "../utils/collection_utils.js";
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
        this._user = user;
        this._password = password;
        this._collection = collection;
        this._shareType = shareType;
        this._share = share;
        this._edit = !!share;
        this._pathMapped = collection.href;

        this._html_scene = get_element_by_id("newshare");
        this._form = /** @type {HTMLFormElement} */ (get_element(this._html_scene, "form"));
        this._sharemapfields = get_element(this._html_scene, "[data-name=sharemapfields]");
        this._shareuser_input = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=shareuser]"));
        this._sharehref_input = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=sharehref]"));
        this._enabled_checkbox = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=enabled]"));
        this._hidden_checkbox = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=hidden]"));
        this._permissions_ro_radio = /** @type {HTMLInputElement} */ (get_element_by_id("newshare_attr_permissions_ro"));
        this._permissions_rw_radio = /** @type {HTMLInputElement} */ (get_element_by_id("newshare_attr_permissions_rw"));
        this._properties_write_allow = /** @type {HTMLInputElement} */ (get_element_by_id("newshare_attr_properties_write_allow"));
        this._properties_write_deny = /** @type {HTMLInputElement} */ (get_element_by_id("newshare_attr_properties_write_deny"));
        this._token_write_warning = /** @type {HTMLElement} */ (get_element(this._html_scene, "[data-name=token_write_warning]"));
        this._conversions_details = /** @type {HTMLDetailsElement} */ (get_element(this._html_scene, "[data-name=conversions]"));
        this._conversions_container = get_element(this._html_scene, "[data-name=conversions_container]");

        this._properties_fieldset = /** @type {HTMLDetailsElement} */ (get_element(this._html_scene, "[data-name=properties_override]"));
        this._displayname_override_enabled = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=displayname_override_enabled]"));
        this._displayname_override_input = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=displayname_override]"));
        this._description_override_enabled = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=description_override_enabled]"));
        this._description_override_input = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=description_override]"));
        this._color_override_enabled = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=color_override_enabled]"));
        this._color_override_input = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=color_override]"));

        this._error_form = get_element(this._html_scene, "[data-name=error]");
        this._submit_btn = get_element(this._html_scene, "[data-name=submit]");
        this._cancel_btn = get_element(this._html_scene, "[data-name=cancel]");

        this._errorHandler = new ErrorHandler(this._error_form);
        this._map_validator = new FormValidator(this._errorHandler);

        this._map_validator.addValidator(this._shareuser_input, () => {
            let conversion = this._get_selected_conversion();
            if (conversion != "none") {
                return validate_non_empty(this._shareuser_input, "Share User")();
            } else {
                return validate_not_empty_or_equals(this._shareuser_input, user, "Share User")();
            }
        });
        this._map_validator.addValidator(this._sharehref_input, validate_href(this._sharehref_input, "Share Href"));

        this._sharehref_input.addEventListener("input", onCleanHREFinput);

        this._displayname_override_enabled.onchange = () => {
            this._displayname_override_input.disabled = !this._displayname_override_enabled.checked;
        };
        this._description_override_enabled.onchange = () => {
            this._description_override_input.disabled = !this._description_override_enabled.checked;
        };
        this._color_override_enabled.onchange = () => {
            this._color_override_input.disabled = !this._color_override_enabled.checked;
        };
    }

    _get_selected_conversion() {
        /** @type {HTMLInputElement | null} */
        let checked = this._conversions_container.querySelector("input[name=conversion]:checked");
        return checked ? checked.value : "none";
    }

    _on_permissions_change() {
        if (this._shareType === "token") {
            if (this._permissions_rw_radio.checked || this._properties_write_allow.checked) {
                this._token_write_warning.classList.remove("hidden");
            } else {
                this._token_write_warning.classList.add("hidden");
            }
        } else {
            this._token_write_warning.classList.add("hidden");
        }
    }

    _on_conversion_change() {
        let conversion = this._get_selected_conversion();
        if (conversion != "none") {
            this._permissions_ro_radio.disabled = true;
            this._permissions_rw_radio.disabled = true;
            this._properties_write_allow.disabled = true;
            this._properties_write_deny.disabled = true;
            this._enabled_checkbox.checked = true;
            this._hidden_checkbox.checked = false;
        } else {
            this._permissions_ro_radio.disabled = false;
            this._permissions_rw_radio.disabled = false;
            this._properties_write_allow.disabled = false;
            this._properties_write_deny.disabled = false;
        }
        if (this._shareType === "map") {
            this._map_validator.validate();
        }
    }

    _oncancel() {
        try {
            pop_scene();
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    _onsubmit() {
        try {
            if (this._shareType === "map") {
                if (!this._map_validator.validate()) {
                    return false;
                }
            }
            let conversion = this._get_selected_conversion();
            let is_conversion = conversion != "none";
            let enabled_by_owner = is_conversion ? true : this._enabled_checkbox.checked;
            let hidden_by_owner = is_conversion ? false : this._hidden_checkbox.checked;
            let permissions = is_conversion ? "r" : (this._permissions_rw_radio.checked ? "rw" : "r");
            let allowPropertiesWrite = this._properties_write_allow.checked;
            if (allowPropertiesWrite) {
                permissions = permissions + "P";
            } else {
                permissions = permissions + "p";
            }
            /** @type {string} */ let conversion_value = conversion;

            /** @type {Object<string, string>} */ let properties = {};
            if (this._displayname_override_enabled.checked) {
                let key = get_property_key(this._collection.type, "DISPLAYNAME");
                if (key) properties[key] = this._displayname_override_input.value;
            }
            if (this._description_override_enabled.checked) {
                let key = get_property_key(this._collection.type, "DESCRIPTION");
                if (key) properties[key] = this._description_override_input.value;
            }
            if (this._color_override_enabled.checked) {
                let key = get_property_key(this._collection.type, "COLOR");
                if (key) properties[key] = this._color_override_input.value + (this._color_override_input.value ? "ff" : "");
            }

            let callback = (/** @type {?string} */ error) => {
                if (!is_current_scene(this)) {
                    return;
                }
                if (error) {
                    this._errorHandler.setError(error);
                } else {
                    // On any share-to-self (currently only bday conversion), invalidate the
                    // collections cache so the virtual calendar appears immediately.
                    if (this._shareuser_input.value === this._user) {
                        collectionsCache.invalidate();
                    }
                    pop_scene();
                }
            };

            let new_share = new Share({
                ShareType: this._shareType,
                PathMapped: this._pathMapped,
                Permissions: permissions,
                EnabledByOwner: enabled_by_owner,
                EnabledByUser: (this._edit && this._share) ? this._share.EnabledByUser : null,
                HiddenByOwner: hidden_by_owner,
                HiddenByUser: (this._edit && this._share) ? this._share.HiddenByUser : null,
                Properties: properties,
                User: (this._edit && this._share) ? this._share.User : this._shareuser_input.value,
                PathOrToken: (this._edit && this._share) ? this._share.PathOrToken : (this._shareType === "map" ? "/" + this._shareuser_input.value + "/" + this._sharehref_input.value + "/" : ""),
                Conversion: conversion_value,
            });

            if (this._edit) {
                if (this._shareType === "map") {
                    update_share_by_map(this._user, this._password, new_share, callback);
                } else {
                    update_share_by_token(this._user, this._password, new_share, callback);
                }
            } else {
                if (this._shareType === "map") {
                    add_share_by_map(this._user, this._password, new_share, callback);
                } else {
                    add_share_by_token(this._user, this._password, new_share, callback);
                }
            }
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    show() {
        this.release();
        this._html_scene.classList.remove("hidden");
        this._html_scene.querySelectorAll("details").forEach(function (details) {
            if (details.dataset.name !== "properties_override") {
                details.open = true;
            } else {
                details.open = false;
            }
        });
        this._cancel_btn.onclick = () => this._oncancel();
        this._form.onsubmit = () => this._onsubmit();

        let onChangeCallback = () => this._on_permissions_change();
        this._permissions_ro_radio.addEventListener("change", onChangeCallback);
        this._permissions_rw_radio.addEventListener("change", onChangeCallback);
        this._properties_write_allow.addEventListener("change", onChangeCallback);
        this._properties_write_deny.addEventListener("change", onChangeCallback);

        /** @type {HTMLHeadingElement} */ let title = /** @type {HTMLHeadingElement} */ (get_element(this._html_scene, "h1"));
        title.textContent = this._edit ? "Edit Share" : "New Share";
        this._submit_btn.textContent = this._edit ? "Save" : "Create";

        this._shareuser_input.value = (this._edit && this._share) ? this._share.User : "";
        this._shareuser_input.disabled = this._edit;
        this._enabled_checkbox.checked = (this._edit && this._share && this._share.EnabledByOwner !== null) ? this._share.EnabledByOwner : true;
        this._hidden_checkbox.checked = (this._edit && this._share && this._share.HiddenByOwner !== null) ? this._share.HiddenByOwner : false;

        let hasWriteProperties = this._collection.has_permission(Permission.WRITE_PROPERTIES);

        if (this._edit || this._shareType === "map") {
            if (hasWriteProperties) {
                this._properties_write_allow.checked = true;
            } else {
                this._properties_write_deny.checked = true;
            }
        } else {
            this._properties_write_deny.checked = true;
        }

        let initial_conversion = (this._edit && this._share && this._share.Conversion) ? this._share.Conversion : "none";

        collectionsCache.getServerFeatures(this._user, this._password, this._errorHandler.setError, (features) => {
            this._conversions_container.innerHTML = "";
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
                    radio.onchange = () => this._on_conversion_change();

                    let label = document.createElement("label");
                    label.htmlFor = id;
                    if (opt === "bday") {
                        label.textContent = "Birthday";
                    } else {
                        label.textContent = opt.charAt(0).toUpperCase() + opt.slice(1);
                    }

                    this._conversions_container.appendChild(radio);
                    this._conversions_container.appendChild(label);
                });

                let is_addressbook = this._collection.type === CollectionType.ADDRESSBOOK;
                if (is_addressbook) {
                    this._conversions_details.classList.remove("hidden");
                    this._conversions_details.open = true;
                } else {
                    this._conversions_details.classList.add("hidden");
                }
            } else {
                this._conversions_details.classList.add("hidden");
            }
            this._on_conversion_change();
        });

        let displayname = this._collection.displayname || "";
        let description = this._collection.description || "";
        let color = this._collection.color || "#ffffff";
        let displayname_override_enabled_value = false;
        let description_override_enabled_value = false;
        let color_override_enabled_value = false;

        if (this._edit && this._share && this._share.Properties) {
            let displayname_key = get_property_key(this._collection.type, "DISPLAYNAME");
            if (displayname_key && this._share.Properties[displayname_key] !== undefined) {
                displayname = this._share.Properties[displayname_key];
                displayname_override_enabled_value = true;
            }
            let description_key = get_property_key(this._collection.type, "DESCRIPTION");
            if (description_key && this._share.Properties[description_key] !== undefined) {
                description = this._share.Properties[description_key];
                description_override_enabled_value = true;
            }
            let color_key = get_property_key(this._collection.type, "COLOR");
            if (color_key && this._share.Properties[color_key] !== undefined) {
                color = this._share.Properties[color_key];
                if (color.length === 9 && color.endsWith("ff")) {
                    color = color.substring(0, 7);
                }
                color_override_enabled_value = true;
            }
        }

        this._displayname_override_enabled.checked = displayname_override_enabled_value;
        this._displayname_override_input.value = displayname;
        this._displayname_override_input.disabled = !displayname_override_enabled_value;

        this._description_override_enabled.checked = description_override_enabled_value;
        this._description_override_input.value = description;
        this._description_override_input.disabled = !description_override_enabled_value;

        this._color_override_enabled.checked = color_override_enabled_value;
        this._color_override_input.value = color;
        this._color_override_input.disabled = !color_override_enabled_value;

        this._properties_fieldset.classList.remove("hidden");
        if (displayname_override_enabled_value || description_override_enabled_value || color_override_enabled_value) {
            this._properties_fieldset.open = true;
        }

        let displayname_key = get_property_key(this._collection.type, "DISPLAYNAME");
        if (!displayname_key) {
            if (this._displayname_override_enabled.parentElement) {
                this._displayname_override_enabled.parentElement.classList.add("hidden");
            }
        } else {
            if (this._displayname_override_enabled.parentElement) {
                this._displayname_override_enabled.parentElement.classList.remove("hidden");
            }
        }
        let description_key = get_property_key(this._collection.type, "DESCRIPTION");
        if (!description_key) {
            if (this._description_override_enabled.parentElement) {
                this._description_override_enabled.parentElement.classList.add("hidden");
            }
        } else {
            if (this._description_override_enabled.parentElement) {
                this._description_override_enabled.parentElement.classList.remove("hidden");
            }
        }

        let color_key = get_property_key(this._collection.type, "COLOR");
        if (!color_key) {
            if (this._color_override_enabled.parentElement) {
                this._color_override_enabled.parentElement.classList.add("hidden");
            }
        } else {
            if (this._color_override_enabled.parentElement) {
                this._color_override_enabled.parentElement.classList.remove("hidden");
            }
        }

        if (this._shareType === "map") {
            if (this._edit && this._share) {
                this._sharehref_input.value = this._share.PathOrToken.split("/").filter(Boolean).pop() || "";
            } else {
                this._sharehref_input.value = random_uuid();
            }
            this._sharehref_input.disabled = this._edit;
            this._sharemapfields.classList.remove("hidden");
            this._map_validator.validate();
        } else {
            this._sharehref_input.value = "";
            this._sharemapfields.classList.add("hidden");
            this._errorHandler.clearError();
        }
        this._on_permissions_change();
    }

    hide() {
        this._html_scene.classList.add("hidden");
        this._cancel_btn.onclick = null;
        this._form.onsubmit = null;
    }

    release() {
    }

    is_transient() { return false; }

    title_object() {
        return extract_title(this._collection);
    }

}
