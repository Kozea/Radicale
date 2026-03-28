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

import { get_principal } from "../api/api.js";
import { ROOT_PATH, SERVER } from "../constants.js";
import { Collection } from "../models/collection.js";
import { collectionsCache } from "../utils/collections_cache.js";
import { ErrorHandler } from "../utils/error.js";
import { FormValidator, validate_non_empty } from "../utils/form_validator.js";
import { get_element, get_element_by_id } from "../utils/misc.js";
import { CollectionsScene } from "./CollectionsScene.js";
import { LoadingScene } from "./LoadingScene.js";
import { Scene, is_current_scene, pop_scene, pop_to_root, push_scene, replace_scene } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class LoginScene {
    constructor() {
        this._html_scene = get_element_by_id("loginscene");
        this._form = get_element(this._html_scene, "[data-name=form]");
        this._user_form = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=user]"));
        this._password_form = /** @type {HTMLInputElement} */ (get_element(this._html_scene, "[data-name=password]"));
        this._error_form = get_element(this._html_scene, "[data-name=error]");
        this._logout_view = get_element_by_id("logoutview");
        this._logout_user_form = get_element(this._logout_view, "[data-name=user]");
        this._logout_btn = get_element(this._logout_view, "[data-name=logout]");
        this._refresh_btn = get_element(this._logout_view, "[data-name=refresh]");

        this._user = "";
        /** @type {?XMLHttpRequest} */ this._principal_req = null;
        this._errorHandler = new ErrorHandler(this._error_form);
        this._validator = new FormValidator(this._errorHandler);
        this._validator.addValidator(this._user_form, validate_non_empty(this._user_form, "Username"));
    }

    _read_form() {
        this._user = this._user_form.value;
    }

    _fill_form() {
        this._user_form.value = this._user;
        this._password_form.value = "";
    }

    /**
     * @param {string} p_user
     * @param {?string} p_password
     */
    _perform_login(p_user, p_password) {
        this._user = p_user;
        this._fill_form();
        // setup logout
        this._logout_view.classList.remove("hidden");
        if (p_password === null) {
            this._logout_btn.classList.add("hidden");
        } else {
            this._logout_btn.classList.remove("hidden");
        }
        this._logout_btn.onclick = () => this._onlogout();
        this._refresh_btn.onclick = () => this._refresh();
        this._logout_user_form.textContent = this._user + "'s Collections";
        // Fetch principal
        let loading_scene = new LoadingScene();
        push_scene(loading_scene);
        this._principal_req = get_principal(this._user, p_password, (/** @type {?Collection} */ principal_collection, error1) => {
            if (!is_current_scene(loading_scene)) {
                return;
            }
            this._principal_req = null;
            if (error1) {
                this._errorHandler.setError(error1);
                pop_scene();
            } else if (principal_collection) {
                // show collections
                let saved_user = this._user;
                this._user = "";
                let collections_scene = new CollectionsScene(
                    saved_user, p_password, principal_collection, (/** @type {?string} */ error1) => {
                        this._errorHandler.setError(error1);
                        this._user = saved_user;
                    });
                replace_scene(collections_scene);
            }
        });
    }

    _onlogin() {
        try {
            collectionsCache.invalidate();
            this._read_form();
            let password = this._password_form.value;
            if (!this._validator.validate()) {
                return false;
            }
            this._perform_login(this._user, password);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    _onlogout() {
        try {
            collectionsCache.invalidate();
            this._user = "";
            pop_to_root();
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    _remove_logout() {
        this._logout_view.classList.add("hidden");
        this._logout_btn.onclick = null;
        this._refresh_btn.onclick = null;
        this._logout_user_form.textContent = "";
    }

    _refresh() {
        // The easiest way to refresh is to push a LoadingScene onto the stack and then pop it
        // forcing the scene below it, the Collections Scene to refresh itself.
        collectionsCache.invalidate();
        push_scene(new LoadingScene());
        pop_scene();
    }

    show() {
        this._remove_logout();
        this._fill_form();
        this._form.onsubmit = () => this._onlogin();
        this._html_scene.classList.remove("hidden");
        this._user_form.focus();

        // Probe for existing authentication (e.g. X-Remote-User)
        // Use fetch with credentials: 'omit' to avoid browser login prompt on 401
        fetch(SERVER + ROOT_PATH, {
            method: 'PROPFIND',
            headers: { 'Depth': '0' },
            credentials: 'omit'
        }).then((response) => {
            if (response.ok) {
                // Authenticated! Now it's safe to call get_principal
                get_principal(null, null, (/** @type {?Collection} */ principal_collection, error) => {
                    if (!error && principal_collection) {
                        let authenticated_user = principal_collection.displayname;
                        if (!authenticated_user) {
                            let href = principal_collection.href.replace(/\/+$/, "");
                            if (href && href !== ROOT_PATH.replace(/\/+$/, "")) {
                                authenticated_user = href.substring(href.lastIndexOf("/") + 1);
                            }
                        }
                        this._perform_login(authenticated_user, null);
                    }
                });
            }
        })["catch"](function () {
            // Ignore error: we are not authenticated or something else went wrong
        });
    }

    hide() {
        this._read_form();
        this._html_scene.classList.add("hidden");
        this._form.onsubmit = null;
    }

    is_transient() { return false; }

    release() {
        // cancel pending requests
        if (this._principal_req !== null) {
            this._principal_req.abort();
            this._principal_req = null;
        }
        this._remove_logout();
    }
}