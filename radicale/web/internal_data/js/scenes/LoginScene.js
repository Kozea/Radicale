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
 * @constructor
 * @implements {Scene}
 */
export class LoginScene {
    constructor() {
        /** @type {HTMLElement} */ let html_scene = get_element_by_id("loginscene");
        /** @type {HTMLElement} */ let form = get_element(html_scene, "[data-name=form]");
        /** @type {HTMLInputElement} */ let user_form = /** @type {HTMLInputElement} */ (get_element(html_scene, "[data-name=user]"));
        /** @type {HTMLInputElement} */ let password_form = /** @type {HTMLInputElement}    */ (get_element(html_scene, "[data-name=password]"));
        /** @type {HTMLElement} */ let error_form = get_element(html_scene, "[data-name=error]");
        /** @type {HTMLElement} */ let logout_view = get_element_by_id("logoutview");
        /** @type {HTMLElement} */ let logout_user_form = get_element(logout_view, "[data-name=user]");
        /** @type {HTMLElement} */ let logout_btn = get_element(logout_view, "[data-name=logout]");
        /** @type {HTMLElement} */ let refresh_btn = get_element(logout_view, "[data-name=refresh]");

        let user = "";
        /** @type {?XMLHttpRequest} */ let principal_req = null;
        let errorHandler = new ErrorHandler(error_form);
        let validator = new FormValidator(errorHandler);
        validator.addValidator(user_form, validate_non_empty(user_form, "Username"));

        function read_form() {
            user = user_form.value;
        }

        function fill_form() {
            user_form.value = user;
            password_form.value = "";
        }

        /**
         * @param {string} p_user
         * @param {?string} p_password
         */
        function perform_login(p_user, p_password) {
            user = p_user;
            fill_form();
            // setup logout
            logout_view.classList.remove("hidden");
            if (p_password === null) {
                logout_btn.classList.add("hidden");
            } else {
                logout_btn.classList.remove("hidden");
            }
            logout_btn.onclick = onlogout;
            refresh_btn.onclick = refresh;
            logout_user_form.textContent = user + "'s Collections";
            // Fetch principal
            let loading_scene = new LoadingScene();
            push_scene(loading_scene);
            principal_req = get_principal(user, p_password, function (/** @type {?Collection} */ principal_collection, error1) {
                if (!is_current_scene(loading_scene)) {
                    return;
                }
                principal_req = null;
                if (error1) {
                    errorHandler.setError(error1);
                    pop_scene();
                } else if (principal_collection) {
                    // show collections
                    let saved_user = user;
                    user = "";
                    let collections_scene = new CollectionsScene(
                        saved_user, p_password, principal_collection, function (/** @type {?string} */ error1) {
                            errorHandler.setError(error1);
                            user = saved_user;
                        });
                    replace_scene(collections_scene);
                }
            });
        }

        function onlogin() {
            try {
                collectionsCache.invalidate();
                read_form();
                let password = password_form.value;
                if (!validator.validate()) {
                    return false;
                }
                perform_login(user, password);
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        let onlogout = function () {
            try {
                collectionsCache.invalidate();
                user = "";
                pop_to_root();
            } catch (err) {
                console.error(err);
            }
            return false;
        };


        function remove_logout() {
            logout_view.classList.add("hidden");
            logout_btn.onclick = null;
            refresh_btn.onclick = null;
            logout_user_form.textContent = "";
        }

        function refresh() {
            // The easiest way to refresh is to push a LoadingScene onto the stack and then pop it
            // forcing the scene below it, the Collections Scene to refresh itself.
            collectionsCache.invalidate();
            push_scene(new LoadingScene());
            pop_scene();
        }

        this.show = function () {
            remove_logout();
            fill_form();
            form.onsubmit = onlogin;
            html_scene.classList.remove("hidden");
            user_form.focus();

            // Probe for existing authentication (e.g. X-Remote-User)
            // Use fetch with credentials: 'omit' to avoid browser login prompt on 401
            fetch(SERVER + ROOT_PATH, {
                method: 'PROPFIND',
                headers: { 'Depth': '0' },
                credentials: 'omit'
            }).then(function (response) {
                if (response.ok) {
                    // Authenticated! Now it's safe to call get_principal
                    get_principal(null, null, function (/** @type {?Collection} */ principal_collection, error) {
                        if (!error && principal_collection) {
                            let authenticated_user = principal_collection.displayname;
                            if (!authenticated_user) {
                                let href = principal_collection.href.replace(/\/+$/, "");
                                if (href && href !== ROOT_PATH.replace(/\/+$/, "")) {
                                    authenticated_user = href.substring(href.lastIndexOf("/") + 1);
                                }
                            }
                            perform_login(authenticated_user, null);
                        }
                    });
                }
            })["catch"](function () {
                // Ignore error: we are not authenticated or something else went wrong
            });
        };
        this.hide = function () {
            read_form();
            html_scene.classList.add("hidden");
            form.onsubmit = null;
        };
        this.release = function () {
            // cancel pending requests
            if (principal_req !== null) {
                principal_req.abort();
                principal_req = null;
            }
            remove_logout();
        };
    }
}