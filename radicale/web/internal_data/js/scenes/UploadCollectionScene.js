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

import { upload_collection } from "../api/api.js";
import { Collection } from "../models/collection.js";
import { collectionsCache } from "../utils/collections_cache.js";
import { ErrorHandler } from "../utils/error.js";
import { FormValidator, validate_files, validate_href } from "../utils/form_validator.js";
import { cleanHREFinput, get_element, get_element_by_id, onCleanHREFinput, random_uuid } from "../utils/misc.js";
import { Scene, pop_scene } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class UploadCollectionScene {
    /**
     * @param {string} user
     * @param {?string} password
     * @param {Collection} collection parent collection
     */
    constructor(user, password, collection) {
        this._user = user;
        this._password = password;
        this._collection = collection;

        this._html_scene = get_element_by_id("uploadcollectionscene");
        this._template = get_element(this._html_scene, "[data-name=filetemplate]");
        this._upload_btn = get_element(this._html_scene, "[data-name=submit]");
        this._close_btn = get_element(this._html_scene, "[data-name=close]");
        this._uploadfile_form = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=uploadfile]"));
        this._uploadfile_lbl = get_element(this._html_scene, "label[for=uploadfile]");
        this._href_form = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=href]"));
        this._href_label = get_element(this._html_scene, "label[for=href]");
        this._hreflimitmsg_html = get_element(this._html_scene, "[data-name=hreflimitmsg]");
        this._pending_html = get_element(this._html_scene, "[data-name=pending]");
        this._error_form = get_element(this._html_scene, ":scope > span[data-name=error]");

        this._files = this._uploadfile_form.files;
        this._href_form.addEventListener("input", onCleanHREFinput);
        this._upload_btn.onclick = () => this._upload_start();
        this._uploadfile_form.onchange = () => this._onfileschange();

        this._href_form.value = "";
        this._href = "";

        this._errorHandler = new ErrorHandler(this._error_form);
        this._validator = new FormValidator(this._errorHandler);

        this._validator.addValidator(this._href_form, validate_href(this._href_form, "HREF"));
        this._validator.addValidator(this._uploadfile_form, validate_files(this._uploadfile_form, "file"));

        /** @type {?XMLHttpRequest} */ this._upload_req = null;
        /** @type {Array<?string>} */ this._results = [];
        /** @type {?Array<HTMLElement>} */ this._nodes = null;
    }

    _upload_start() {
        try {
            if (!this._validator.validate()) {
                return false;
            }
            if (!this._files) {
                return false;
            }
            this._read_form();
            this._uploadfile_form.classList.add("hidden");
            this._uploadfile_lbl.classList.add("hidden");
            this._href_form.classList.add("hidden");
            this._href_label.classList.add("hidden");
            this._hreflimitmsg_html.classList.add("hidden");
            this._upload_btn.classList.add("hidden");
            this._close_btn.classList.add("hidden");

            this._pending_html.classList.remove("hidden");

            this._nodes = [];
            for (let i = 0; i < this._files.length; i++) {
                let file = this._files[i];
                let node = /** @type {HTMLElement} */ (this._template.cloneNode(true));
                node.classList.remove("hidden");
                let name_form = get_element(node, "[data-name=name]");
                name_form.textContent = file.name;
                node.classList.remove("hidden");
                this._nodes.push(node);
                this._updateFileStatus(i);
                if (this._template.parentNode) {
                    this._template.parentNode.insertBefore(node, this._template);
                }
            }
            this._upload_next();
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    _upload_next() {
        if (!this._files) {
            return;
        }
        try {
            if (this._files.length === this._results.length) {
                this._pending_html.classList.add("hidden");
                this._close_btn.classList.remove("hidden");
                return;
            } else {
                let file = this._files[this._results.length];
                if (this._files.length > 1 || this._href.length == 0) {
                    this._href = random_uuid();
                }
                let upload_href = this._collection.href + this._href + "/";
                this._upload_req = upload_collection(this._user, this._password, upload_href, file, (result) => {
                    this._upload_req = null;
                    this._results.push(result);
                    this._updateFileStatus(this._results.length - 1);
                    this._upload_next();
                });
            }
        } catch (err) {
            console.error(err);
        }
    }

    _onclose() {
        try {
            if (this._results.length > 0) {
                collectionsCache.invalidate();
            }
            pop_scene();
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    /**
     * @param {number} i
     */
    _updateFileStatus(i) {
        if (this._nodes === null) {
            return;
        }
        /** @type {HTMLElement} */ let file_success_form = get_element(this._nodes[i], "[data-name=success]");
        /** @type {HTMLElement} */ let file_error_form = get_element(this._nodes[i], "[data-name=error]");
        if (this._results.length > i) {
            if (this._results[i]) {
                file_success_form.classList.add("hidden");
                file_error_form.textContent = "Error: " + this._results[i];
                this._error_form.classList.remove("hidden");
            } else {
                file_success_form.classList.remove("hidden");
                file_error_form.classList.add("hidden");
            }
        } else {
            file_success_form.classList.add("hidden");
            file_error_form.classList.add("hidden");
        }
    }

    _read_form() {
        cleanHREFinput(this._href_form);
        this._href = this._href_form.value.trim().toLowerCase();
        this._files = this._uploadfile_form.files;
        return true;
    }

    _onfileschange() {
        this._files = this._uploadfile_form.files;
        if (this._files && this._files.length > 1) {
            this._hreflimitmsg_html.classList.remove("hidden");
            this._href_form.classList.add("hidden");
            this._href_label.classList.add("hidden");
            this._href_form.value = random_uuid(); // fake HREF, will be replaced on upload
        } else {
            this._hreflimitmsg_html.classList.add("hidden");
            this._href_form.classList.remove("hidden");
            this._href_label.classList.remove("hidden");
            if (this._files && this._files.length > 0) {
                this._href_form.value = this._files[0].name.replace(/\.(ics|vcf)$/, '');
            } else {
                this._href_form.value = "";
            }
        }
        return false;
    }

    show() {
        this._html_scene.classList.remove("hidden");
        this._close_btn.onclick = () => this._onclose();
    }

    hide() {
        this._html_scene.classList.add("hidden");
        this._close_btn.classList.remove("hidden");
        this._upload_btn.classList.remove("hidden");
        this._uploadfile_form.classList.remove("hidden");
        this._uploadfile_lbl.classList.remove("hidden");
        this._href_form.classList.remove("hidden");
        this._href_label.classList.remove("hidden");
        this._hreflimitmsg_html.classList.add("hidden");
        this._pending_html.classList.add("hidden");
        this._errorHandler.clearError();
        this._close_btn.onclick = null;
        this._upload_btn.onclick = null;
        this._href_form.value = "";
        this._uploadfile_form.value = "";
        if (this._nodes == null) {
            return;
        }
        this._nodes.forEach(function (node) {
            if (node.parentNode) {
                node.parentNode.removeChild(node);
            }
        });
        this._nodes = null;
    }

    is_transient() { return false; }

    release() {
        if (this._upload_req !== null) {
            this._upload_req.abort();
            this._upload_req = null;
        }
    }
}