/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2017-2024 Unrud <unrud@outlook.com>
 * Copyright © 2023-2024 Matthew Hana <matthew.hana@gmail.com>
 * Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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

import { Scene, push_scene, pop_scene, scene_stack } from "./scene_manager.js";
import { LoadingScene } from "./LoadingScene.js";
import { get_principal, discover_server_features } from "./api.js";
import { CollectionsScene } from "./CollectionsScene.js";
import { maybe_enable_sharing_options } from "./ShareCollectionScene.js";

/**
 * @constructor
 * @implements {Scene}
 */
export function LoginScene() {
    let html_scene = document.getElementById("loginscene");
    let form = html_scene.querySelector("[data-name=form]");
    let user_form = html_scene.querySelector("[data-name=user]");
    let password_form = html_scene.querySelector("[data-name=password]");
    let error_form = html_scene.querySelector("[data-name=error]");
    let logout_view = document.getElementById("logoutview");
    let logout_user_form = logout_view.querySelector("[data-name=user]");
    let logout_btn = logout_view.querySelector("[data-name=logout]");
    let refresh_btn = logout_view.querySelector("[data-name=refresh]");

    /** @type {?number} */ let scene_index = null;
    let user = "";
    let error = "";
    /** @type {?XMLHttpRequest} */ let principal_req = null;

    function read_form() {
        user = user_form.value;
    }

    function fill_form() {
        user_form.value = user;
        password_form.value = "";
        if(error){
            error_form.textContent = "Error: " + error;
            error_form.classList.remove("hidden");
        }else{
            error_form.classList.add("hidden");
        }
    }

    function onlogin() {
        try {
            read_form();
            let password = password_form.value;
            if (user) {
                error = "";
                // setup logout
                logout_view.classList.remove("hidden");
                logout_btn.onclick = onlogout;
                refresh_btn.onclick = refresh;
                logout_user_form.textContent = user + "'s Collections";
                // Fetch principal
                let loading_scene = new LoadingScene();
                push_scene(loading_scene, false);
                principal_req = get_principal(user, password, function(collection, error1) {
                    if (scene_index === null) {
                        return;
                    }
                    principal_req = null;
                    if (error1) {
                        error = error1;
                        pop_scene(scene_index);
                    } else {
                        // show collections
                        let saved_user = user;
                        user = "";
                        let collections_scene = new CollectionsScene(
                            saved_user, password, collection, function(error1) {
                                error = error1;
                                user = saved_user;
                            });
                        discover_server_features(saved_user, password, maybe_enable_sharing_options);
                        push_scene(collections_scene, true);
                    }
                });
            } else {
                error = "Username is empty";
                fill_form();
            }
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function onlogout() {
        try {
            if (scene_index === null) {
                return false;
            }
            user = "";
            pop_scene(scene_index);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    function remove_logout() {
        logout_view.classList.add("hidden");
        logout_btn.onclick = null;
        refresh_btn.onclick = null;
        logout_user_form.textContent = "";
    }

    function refresh(){
        //The easiest way to refresh is to push a LoadingScene onto the stack and then pop it
        //forcing the scene below it, the Collections Scene to refresh itself.
        push_scene(new LoadingScene(), false);
        pop_scene(scene_stack.length-2);
    }

    this.show = function() {
        remove_logout();
        fill_form();
        form.onsubmit = onlogin;
        html_scene.classList.remove("hidden");
        scene_index = scene_stack.length - 1;
        user_form.focus();
    };
    this.hide = function() {
        read_form();
        html_scene.classList.add("hidden");
        form.onsubmit = null;
    };
    this.release = function() {
        scene_index = null;
        // cancel pending requests
        if (principal_req !== null) {
            principal_req.abort();
            principal_req = null;
        }
        remove_logout();
    };
}