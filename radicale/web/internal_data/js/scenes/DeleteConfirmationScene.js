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
import { get_element, get_element_by_id } from "../utils/misc.js";
import { LoadingScene } from "./LoadingScene.js";
import { Scene, is_current_scene, pop_scene, push_scene } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class DeleteConfirmationScene {
    /**
     * @param {string} user
     * @param {?string} password
     * @param {string} header_title
     * @param {any} item
     * @param {string} item_title
     * @param {function} delete_action
     * @param {boolean} needsconfirmation
     * @param {function} [on_success]
     */
    constructor(user, password, header_title, item, item_title, delete_action, needsconfirmation, on_success) {
        this._user = user;
        this._password = password;
        this._item = item;
        this._item_title = item_title;
        this._delete_action = delete_action;
        this._needsconfirmation = needsconfirmation;
        this._on_success = on_success;

        this._html_scene = get_element_by_id("deleteconfirmationscene");
        /** @type {HTMLElement} */ let header_html = get_element(this._html_scene, "[data-name=headertitle]");
        if (header_html) header_html.textContent = header_title;
        this._title_form = get_element(this._html_scene, "[data-name=title]");
        this._error_form = get_element(this._html_scene, "[data-name=error]");
        this._confirmation_prompt = get_element(this._html_scene, "[data-name=confirmationprompt]");
        this._confirmation_txt = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=confirmationtxt]"));
        this._delete_confirmation_lbl = get_element(this._html_scene, "[data-name=deleteconfirmationtext]");
        this._delete_btn = get_element(this._html_scene, "[data-name=delete]");
        this._cancel_btn = get_element(this._html_scene, "[data-name=cancel]");

        if (needsconfirmation) {
            this._delete_confirmation_lbl.innerHTML = DELETE_CONFIRMATION_TEXT;
            this._confirmation_txt.value = "";
            this._confirmation_txt.addEventListener("keydown", (e) => this._onkeydown(e));
            this._confirmation_prompt.classList.remove("hidden");
            this._confirmation_txt.classList.remove("hidden");
        } else {
            this._confirmation_prompt.classList.add("hidden");
            this._confirmation_txt.classList.add("hidden");
        }

        /** @type {?XMLHttpRequest} */ this._delete_req = null;

        this._errorHandler = new ErrorHandler(this._error_form);
        this._validator = new FormValidator(this._errorHandler);

        if (needsconfirmation) {
            this._validator.addValidator(this._confirmation_txt, validate_equals(this._confirmation_txt, DELETE_CONFIRMATION_TEXT, "confirmation"));
        }
    }

    _ondelete() {
        if (this._needsconfirmation && !this._validator.validate()) {
            return false;
        }
        try {
            let loading_scene = new LoadingScene();
            push_scene(loading_scene);
            this._delete_req = this._delete_action(this._user, this._password, this._item, (/** @type {?string} */ error1) => {
                if (!is_current_scene(loading_scene)) {
                    return;
                }
                this._delete_req = null;
                if (error1) {
                    pop_scene();
                    this._errorHandler.setError(error1);
                } else {
                    pop_scene();
                    if (this._on_success) {
                        this._on_success();
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

    _oncancel() {
        try {
            pop_scene();
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    /** @param {KeyboardEvent} event */
    _onkeydown(event) {
        if (event.code !== "Enter") {
            return;
        }
        this._ondelete();
    }

    show() {
        this.release();
        this._html_scene.classList.remove("hidden");
        this._title_form.textContent = this._item_title;
        this._delete_btn.onclick = () => this._ondelete();
        this._cancel_btn.onclick = () => this._oncancel();
        this._validator.validate();
    }

    hide() {
        this._html_scene.classList.add("hidden");
        this._cancel_btn.onclick = null;
        this._delete_btn.onclick = null;
    }

    is_transient() { return false; }

    release() {
        if (this._delete_req !== null) {
            this._delete_req.abort();
            this._delete_req = null;
        }
    }

    title_object() { return ""; }
}