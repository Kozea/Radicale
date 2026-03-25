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
        /** @type {HTMLElement} */ let html_scene = get_element_by_id("uploadcollectionscene");
        /** @type {HTMLElement} */ let template = get_element(html_scene, "[data-name=filetemplate]");
        /** @type {HTMLElement} */ let upload_btn = get_element(html_scene, "[data-name=submit]");
        /** @type {HTMLElement} */ let close_btn = get_element(html_scene, "[data-name=close]");
        /** @type {HTMLInputElement} */ let uploadfile_form = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=uploadfile]"));
        /** @type {HTMLElement} */ let uploadfile_lbl = get_element(html_scene, "label[for=uploadfile]");
        /** @type {HTMLInputElement} */ let href_form = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=href]"));
        /** @type {HTMLElement} */ let href_label = get_element(html_scene, "label[for=href]");
        /** @type {HTMLElement} */ let hreflimitmsg_html = get_element(html_scene, "[data-name=hreflimitmsg]");
        /** @type {HTMLElement} */ let pending_html = get_element(html_scene, "[data-name=pending]");
        /** @type {HTMLElement} */ let error_form = get_element(html_scene, ":scope > span[data-name=error]");

        let files = uploadfile_form.files;
        href_form.addEventListener("input", onCleanHREFinput);
        upload_btn.onclick = upload_start;
        uploadfile_form.onchange = onfileschange;

        href_form.value = "";
        let href = "";

        let errorHandler = new ErrorHandler(error_form);
        let validator = new FormValidator(errorHandler);

        validator.addValidator(href_form, validate_href(href_form, "HREF"));
        validator.addValidator(uploadfile_form, validate_files(uploadfile_form, "file"));

        /** @type {?XMLHttpRequest} */ let upload_req = null;
        /** @type {Array<?string>} */ let results = [];
        /** @type {?Array<HTMLElement>} */ let nodes = null;

        function upload_start() {
            try {
                if (!validator.validate()) {
                    return false;
                }
                if (!files) {
                    return false;
                }
                read_form();
                uploadfile_form.classList.add("hidden");
                uploadfile_lbl.classList.add("hidden");
                href_form.classList.add("hidden");
                href_label.classList.add("hidden");
                hreflimitmsg_html.classList.add("hidden");
                upload_btn.classList.add("hidden");
                close_btn.classList.add("hidden");

                pending_html.classList.remove("hidden");

                nodes = [];
                for (let i = 0; i < files.length; i++) {
                    let file = files[i];
                    let node = /** @type {HTMLElement} */ (template.cloneNode(true));
                    node.classList.remove("hidden");
                    let name_form = get_element(node, "[data-name=name]");
                    name_form.textContent = file.name;
                    node.classList.remove("hidden");
                    nodes.push(node);
                    updateFileStatus(i);
                    if (template.parentNode) {
                        template.parentNode.insertBefore(node, template);
                    }
                }
                upload_next();
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        function upload_next() {
            if (!files) {
                return;
            }
            try {
                if (files.length === results.length) {
                    pending_html.classList.add("hidden");
                    close_btn.classList.remove("hidden");
                    return;
                } else {
                    let file = files[results.length];
                    if (files.length > 1 || href.length == 0) {
                        href = random_uuid();
                    }
                    let upload_href = collection.href + href + "/";
                    upload_req = upload_collection(user, password, upload_href, file, function (result) {
                        upload_req = null;
                        results.push(result);
                        updateFileStatus(results.length - 1);
                        upload_next();
                    });
                }
            } catch (err) {
                console.error(err);
            }
        }

        function onclose() {
            try {
                if (results.length > 0) {
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
        function updateFileStatus(i) {
            if (nodes === null) {
                return;
            }
            /** @type {HTMLElement} */ let file_success_form = get_element(nodes[i], "[data-name=success]");
            /** @type {HTMLElement} */ let file_error_form = get_element(nodes[i], "[data-name=error]");
            if (results.length > i) {
                if (results[i]) {
                    file_success_form.classList.add("hidden");
                    file_error_form.textContent = "Error: " + results[i];
                    error_form.classList.remove("hidden");
                } else {
                    file_success_form.classList.remove("hidden");
                    file_error_form.classList.add("hidden");
                }
            } else {
                file_success_form.classList.add("hidden");
                file_error_form.classList.add("hidden");
            }
        }

        function read_form() {
            cleanHREFinput(href_form);
            href = href_form.value.trim().toLowerCase();
            files = uploadfile_form.files;
            return true;
        }

        function onfileschange() {
            files = uploadfile_form.files;
            if (files && files.length > 1) {
                hreflimitmsg_html.classList.remove("hidden");
                href_form.classList.add("hidden");
                href_label.classList.add("hidden");
                href_form.value = random_uuid(); // fake HREF, will be replaced on upload
            } else {
                hreflimitmsg_html.classList.add("hidden");
                href_form.classList.remove("hidden");
                href_label.classList.remove("hidden");
                if (files && files.length > 0) {
                    href_form.value = files[0].name.replace(/\.(ics|vcf)$/, '');
                } else {
                    href_form.value = "";
                }
            }
            return false;
        }

        this.show = function () {
            html_scene.classList.remove("hidden");
            close_btn.onclick = onclose;
        };

        this.hide = function () {
            html_scene.classList.add("hidden");
            close_btn.classList.remove("hidden");
            upload_btn.classList.remove("hidden");
            uploadfile_form.classList.remove("hidden");
            uploadfile_lbl.classList.remove("hidden");
            href_form.classList.remove("hidden");
            href_label.classList.remove("hidden");
            hreflimitmsg_html.classList.add("hidden");
            pending_html.classList.add("hidden");
            errorHandler.clearError();
            close_btn.onclick = null;
            upload_btn.onclick = null;
            href_form.value = "";
            uploadfile_form.value = "";
            if (nodes == null) {
                return;
            }
            nodes.forEach(function (node) {
                if (node.parentNode) {
                    node.parentNode.removeChild(node);
                }
            });
            nodes = null;
        };
        this.release = function () {
            if (upload_req !== null) {
                upload_req.abort();
                upload_req = null;
            }
        };
    }
}