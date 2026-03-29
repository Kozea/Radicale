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

import { create_collection, edit_collection } from "../api/api.js";
import { COLOR_RE } from "../constants.js";
import { Collection, CollectionType } from "../models/collection.js";
import { collectionsCache } from "../utils/collections_cache.js";
import { ErrorHandler } from "../utils/error.js";
import { FormValidator, validate_color, validate_href } from "../utils/form_validator.js";
import { cleanHREFinput, get_element, get_element_by_id, onCleanHREFinput, random_hex, random_uuid } from "../utils/misc.js";
import { LoadingScene } from "./LoadingScene.js";
import { Scene, is_current_scene, pop_scene, pop_to_parent, push_scene } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class CreateEditCollectionScene {
    /**
     * @param {string} user
     * @param {?string} password
     * @param {Collection} collection if it's a principal collection, a new
     *                                collection will be created inside of it.
     *                                Otherwise the collection will be edited.
     */
    constructor(user, password, collection) {
        this._user = user;
        this._password = password;
        this._collection = collection;
        this._edit = collection.type !== CollectionType.PRINCIPAL;

        this._html_scene = get_element_by_id(this._edit ? "editcollectionscene" : "createcollectionscene");
        this._title_form = this._edit ? get_element(this._html_scene, "[data-name=title]") : null;
        this._error_form = get_element(this._html_scene, "[data-name=error]");
        this._href_form = this._edit ? null : /** @type {HTMLInputElement} */(get_element(this._html_scene, "[data-name=href]"));
        this._displayname_form = /** @type {HTMLInputElement} */(get_element(this._html_scene, "[data-name=displayname]"));
        this._description_form = /** @type {HTMLInputElement} */(get_element(this._html_scene, "[data-name=description]"));
        this._source_form = /** @type {HTMLInputElement} */(get_element(this._html_scene, "[data-name=source]"));
        this._source_label = get_element(this._html_scene, "label[for$=source]");
        this._type_form = /** @type {HTMLSelectElement} */(get_element(this._html_scene, "[data-name=type]"));
        this._color_form = /** @type {HTMLInputElement} */(get_element(this._html_scene, "[data-name=color]"));
        this._submit_btn = get_element(this._html_scene, "[data-name=submit]");
        this._cancel_btn = get_element(this._html_scene, "[data-name=cancel]");

        /** @type {?XMLHttpRequest} */ this._create_edit_req = null;
        /** @type {?HTMLSelectElement} */ this._saved_type_form = null;

        this._errorHandler = new ErrorHandler(this._error_form);
        this._validator = new FormValidator(this._errorHandler);

        if (!this._edit && this._href_form) {
            this._validator.addValidator(this._href_form, validate_href(this._href_form, "HREF"));
        }
        this._validator.addValidator(this._color_form, validate_color(this._color_form, "Color"));

        this._href = this._edit ? collection.href : collection.href + random_uuid() + "/";
        this._displayname = this._edit ? collection.displayname : "";
        this._description = this._edit ? collection.description : "";
        this._source = this._edit ? collection.source : "";
        this._type = this._edit ? collection.type : CollectionType.CALENDAR_JOURNAL_TASKS;
        this._color = this._edit && collection.color ? collection.color : "#" + random_hex(6);

        if (!this._edit && this._href_form) {
            this._href_form.addEventListener("input", onCleanHREFinput);
        }
    }

    _remove_invalid_types() {
        if (!this._edit) {
            return;
        }
        /** @type {HTMLOptionsCollection} */ let options = this._type_form.options;
        let valid_type_options = CollectionType.valid_options_for_type(this._type);
        for (let i = options.length - 1; i >= 0; i--) {
            if (valid_type_options.indexOf(options[i].value) < 0) {
                options.remove(i);
            }
        }
    }

    _read_form() {
        if (!this._edit && this._href_form) {
            cleanHREFinput(this._href_form);
            let newhreftxtvalue = this._href_form.value.trim().toLowerCase();
            this._href = this._collection.href + newhreftxtvalue + "/";
        }
        this._displayname = this._displayname_form.value;
        this._description = this._description_form.value;
        this._source = this._source_form.value;
        this._type = this._type_form.value;
        this._color = this._color_form.value;
        return true;
    }

    _fill_form() {
        if (!this._edit && this._href_form) {
            this._href_form.value = random_uuid();
        }
        this._displayname_form.value = this._displayname;
        this._description_form.value = this._description;
        this._source_form.value = this._source;
        this._type_form.value = this._type;
        this._color_form.value = this._color;
        this._onTypeChange(null);
        this._type_form.addEventListener("change", (e) => this._onTypeChange(e));
    }

    _onsubmit() {
        try {
            if (!this._validator.validate()) {
                return false;
            }
            this._read_form();
            let sane_color = this._color.trim();
            if (sane_color) {
                /** @type {?RegExpExecArray} */ let match = COLOR_RE.exec(sane_color);
                if (match) {
                    sane_color = match[1];
                }
            }
            let loading_scene = new LoadingScene();
            push_scene(loading_scene);
            let collection = new Collection(this._href, this._type, this._displayname, this._description, sane_color, 0, 0, this._source);
            let callback = (/** @type {?string} */ error1) => {
                if (!is_current_scene(loading_scene)) {
                    return;
                }
                this._create_edit_req = null;
                if (error1) {
                    this._errorHandler.setError(error1);
                    pop_scene();
                } else {
                    collectionsCache.invalidate();
                    pop_to_parent();
                }
            };
            if (this._edit) {
                this._create_edit_req = edit_collection(this._user, this._password, collection, callback);
            } else {
                this._create_edit_req = create_collection(this._user, this._password, collection, callback);
            }
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    _oncancel() {
        try {
            pop_scene();
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    /**
     * @param {?Event} _e
     */
    _onTypeChange(_e) {
        if (this._type_form.value == CollectionType.WEBCAL) {
            this._source_label.classList.remove("hidden");
            this._source_form.classList.remove("hidden");
        } else {
            this._source_label.classList.add("hidden");
            this._source_form.classList.add("hidden");
        }
    }

    show() {
        this.release();
        // Clone type_form because it's impossible to hide options without removing them
        this._saved_type_form = this._type_form;
        this._type_form = /** @type {HTMLSelectElement} */ (this._type_form.cloneNode(true));
        if (this._saved_type_form.parentNode) {
            this._saved_type_form.parentNode.replaceChild(this._type_form, this._saved_type_form);
        }
        this._remove_invalid_types();
        this._html_scene.classList.remove("hidden");
        if (this._edit && this._title_form) {
            this._title_form.textContent = this._collection.displayname || this._collection.href;
        }
        this._fill_form();
        this._submit_btn.onclick = () => this._onsubmit();
        this._cancel_btn.onclick = () => this._oncancel();
        this._validator.validate();
    }

    hide() {
        this._read_form();
        this._html_scene.classList.add("hidden");
        // restore type_form
        if (this._type_form.parentNode && this._saved_type_form) {
            this._type_form.parentNode.replaceChild(this._saved_type_form, this._type_form);
            this._type_form = this._saved_type_form;
        }
        this._saved_type_form = null;
        this._submit_btn.onclick = null;
        this._cancel_btn.onclick = null;
    }

    is_transient() { return false; }

    release() {
        if (this._create_edit_req !== null) {
            this._create_edit_req.abort();
            this._create_edit_req = null;
        }
    }
}