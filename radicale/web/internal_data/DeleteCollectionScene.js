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
import { Collection } from "./models.js";
import { DELETE_CONFIRMATION_TEXT } from "./constants.js";
import { LoadingScene } from "./LoadingScene.js";
import { delete_collection } from "./api.js";

/**
 * @constructor
 * @implements {Scene}
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection
 */
export function DeleteCollectionScene(user, password, collection) {
    let html_scene = document.getElementById("deletecollectionscene");
    let title_form = html_scene.querySelector("[data-name=title]");
    let error_form = html_scene.querySelector("[data-name=error]");
    let confirmation_txt = html_scene.querySelector("[data-name=confirmationtxt]");
    let delete_confirmation_lbl = html_scene.querySelector("[data-name=deleteconfirmationtext]");
    let delete_btn = html_scene.querySelector("[data-name=delete]");
    let cancel_btn = html_scene.querySelector("[data-name=cancel]");

    delete_confirmation_lbl.innerHTML = DELETE_CONFIRMATION_TEXT;
    confirmation_txt.value = "";
    confirmation_txt.addEventListener("keydown", onkeydown);

    /** @type {?number} */ let scene_index = null;
    /** @type {?XMLHttpRequest} */ let delete_req = null;
    let error = "";

    function ondelete() {
        let confirmation_text_value = confirmation_txt.value;
        if(confirmation_text_value != DELETE_CONFIRMATION_TEXT){
            alert("Please type the confirmation text to delete this collection.");
            return;
        }
        try {
            let loading_scene = new LoadingScene();
            push_scene(loading_scene);
            delete_req = delete_collection(user, password, collection, function(error1) {
                if (scene_index === null) {
                    return;
                }
                delete_req = null;
                if (error1) {
                    error = error1;
                    pop_scene(scene_index);
                } else {
                    pop_scene(scene_index - 1);
                }
            });
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function oncancel() {
        try {
            pop_scene(scene_index - 1);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function onkeydown(event){
        if (event.keyCode !== 13) {
            return;
        }
        ondelete();
    }

    this.show = function() {
        this.release();
        scene_index = scene_stack.length - 1;
        html_scene.classList.remove("hidden");
        title_form.textContent = collection.displayname || collection.href;
        delete_btn.onclick = ondelete;
        cancel_btn.onclick = oncancel;
        if(error){
            error_form.textContent = "Error: " + error;
            error_form.classList.remove("hidden");
        }else{
            error_form.classList.add("hidden");
        }

    };
    this.hide = function() {
        html_scene.classList.add("hidden");
        cancel_btn.onclick = null;
        delete_btn.onclick = null;
    };
    this.release = function() {
        scene_index = null;
        if (delete_req !== null) {
            delete_req.abort();
            delete_req = null;
        }
    };
}