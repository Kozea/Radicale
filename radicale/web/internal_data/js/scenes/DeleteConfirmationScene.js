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

import { DELETE_CONFIRMATION_TEXT } from "../constants.js";
import { collectionsCache } from "../utils/collections_cache.js";
import { ErrorHandler } from "../utils/error.js";
import { FormValidator, validate_equals } from "../utils/form_validator.js";
import { LoadingScene } from "./LoadingScene.js";
import { Scene, is_current_scene, pop_scene, push_scene } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class DeleteConfirmationScene {
    /**
     * @param {string} user
     * @param {string} password
     * @param {string} header_title
     * @param {any} item
     * @param {string} item_title
     * @param {function} delete_action
     * @param {boolean} needsconfirmation
     * @param {function} [on_success]
     */
    constructor(user, password, header_title, item, item_title, delete_action, needsconfirmation, on_success) {
        /** @type {HTMLElement} */ let html_scene = document.getElementById("deleteconfirmationscene");
        /** @type {HTMLElement} */ let header_html = html_scene.querySelector("[data-name=headertitle]");
        if (header_html) header_html.textContent = header_title;
        /** @type {HTMLElement} */ let title_form = html_scene.querySelector("[data-name=title]");
        /** @type {HTMLElement} */ let error_form = html_scene.querySelector("[data-name=error]");
        /** @type {HTMLElement} */ let confirmation_prompt = html_scene.querySelector("[data-name=confirmationprompt]");
        /** @type {HTMLInputElement} */ let confirmation_txt = html_scene.querySelector("[data-name=confirmationtxt]");
        /** @type {HTMLElement} */ let delete_confirmation_lbl = html_scene.querySelector("[data-name=deleteconfirmationtext]");
        /** @type {HTMLElement} */ let delete_btn = html_scene.querySelector("[data-name=delete]");
        /** @type {HTMLElement} */ let cancel_btn = html_scene.querySelector("[data-name=cancel]");

        if (needsconfirmation) {
            delete_confirmation_lbl.innerHTML = DELETE_CONFIRMATION_TEXT;
            confirmation_txt.value = "";
            confirmation_txt.addEventListener("keydown", onkeydown);
            confirmation_prompt.classList.remove("hidden");
            confirmation_txt.classList.remove("hidden");
        } else {
            confirmation_prompt.classList.add("hidden");
            confirmation_txt.classList.add("hidden");
            confirmation_txt.removeEventListener("keydown", onkeydown);
        }

        /** @type {?XMLHttpRequest} */ let delete_req = null;

        let errorHandler = new ErrorHandler(error_form);
        let validator = new FormValidator(errorHandler);

        if (needsconfirmation) {
            validator.addValidator(confirmation_txt, validate_equals(confirmation_txt, DELETE_CONFIRMATION_TEXT, "confirmation"));
        }

        function ondelete() {
            if (needsconfirmation && !validator.validate()) {
                return false;
            }
            try {
                let loading_scene = new LoadingScene();
                push_scene(loading_scene);
                delete_req = delete_action(user, password, item, function (error1) {
                    if (!is_current_scene(loading_scene)) {
                        return;
                    }
                    delete_req = null;
                    if (error1) {
                        pop_scene();
                        errorHandler.setError(error1);
                    } else {
                        pop_scene();
                        if (on_success) {
                            on_success();
                        } else {
                            collectionsCache.invalidate();
                            pop_scene();
                        }
                    }
                });
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        function oncancel() {
            try {
                pop_scene();
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        function onkeydown(event) {
            if (event.keyCode !== 13) {
                return;
            }
            ondelete();
        }

        this.show = function () {
            this.release();
            html_scene.classList.remove("hidden");
            title_form.textContent = item_title;
            delete_btn.onclick = ondelete;
            cancel_btn.onclick = oncancel;
            validator.validate();
        };
        this.hide = function () {
            html_scene.classList.add("hidden");
            cancel_btn.onclick = null;
            delete_btn.onclick = null;
        };
        this.release = function () {
            if (delete_req !== null) {
                delete_req.abort();
                delete_req = null;
            }
        };
    }
}