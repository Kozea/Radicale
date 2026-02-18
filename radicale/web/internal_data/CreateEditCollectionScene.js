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
import { Collection, CollectionType } from "./models.js";
import { random_uuid, random_hex, cleanHREFinput, isValidHREF } from "./utils.js";
import { LoadingScene } from "./LoadingScene.js";
import { COLOR_RE } from "./constants.js";
import { create_collection, edit_collection } from "./api.js";

/**
 * @constructor
 * @implements {Scene}
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection if it's a principal collection, a new
 *                                collection will be created inside of it.
 *                                Otherwise the collection will be edited.
 */
export function CreateEditCollectionScene(user, password, collection) {
    let edit = collection.type !== CollectionType.PRINCIPAL;
    let html_scene = document.getElementById(edit ? "editcollectionscene" : "createcollectionscene");
    let title_form = edit ? html_scene.querySelector("[data-name=title]") : null;
    let error_form = html_scene.querySelector("[data-name=error]");
    let href_form = html_scene.querySelector("[data-name=href]");
    let href_label = html_scene.querySelector("label[for=href]");
    let displayname_form = html_scene.querySelector("[data-name=displayname]");
    let displayname_label = html_scene.querySelector("label[for=displayname]");
    let description_form = html_scene.querySelector("[data-name=description]");
    let description_label = html_scene.querySelector("label[for=description]");
    let source_form = html_scene.querySelector("[data-name=source]");
    let source_label = html_scene.querySelector("label[for=source]");
    let type_form = html_scene.querySelector("[data-name=type]");
    let type_label = html_scene.querySelector("label[for=type]");
    let color_form = html_scene.querySelector("[data-name=color]");
    let color_label = html_scene.querySelector("label[for=color]");
    let submit_btn = html_scene.querySelector("[data-name=submit]");
    let cancel_btn = html_scene.querySelector("[data-name=cancel]");


    /** @type {?number} */ let scene_index = null;
    /** @type {?XMLHttpRequest} */ let create_edit_req = null;
    let error = "";
    /** @type {?Element} */ let saved_type_form = null;

    let href = edit ? collection.href : collection.href + random_uuid() + "/";
    let displayname = edit ? collection.displayname : "";
    let description = edit ? collection.description : "";
    let source = edit ? collection.source : "";
    let type = edit ? collection.type : CollectionType.CALENDAR_JOURNAL_TASKS;
    let color = edit && collection.color ? collection.color : "#" + random_hex(6);

    if(!edit){
        href_form.addEventListener("keydown", cleanHREFinput);
    }

    function remove_invalid_types() {
        if (!edit) {
            return;
        }
        /** @type {HTMLOptionsCollection} */ let options = type_form.options;
        // remove all options that are not supersets
        let valid_type_options = CollectionType.valid_options_for_type(type);
        for (let i = options.length - 1; i >= 0; i--) {
            if (valid_type_options.indexOf(options[i].value) < 0) {
                options.remove(i);
            }
        }
    }

    function read_form() {
        if(!edit){
            cleanHREFinput(href_form);
            let newhreftxtvalue = href_form.value.trim().toLowerCase();
            if(!isValidHREF(newhreftxtvalue)){
                alert("You must enter a valid HREF");
                return false;
            }
            href = collection.href + newhreftxtvalue + "/";
        }
        displayname = displayname_form.value;
        description = description_form.value;
        source = source_form.value;
        type = type_form.value;
        color = color_form.value;
        return true;
    }

    function fill_form() {
        if(!edit){
            href_form.value = random_uuid();
        }
        displayname_form.value = displayname;
        description_form.value = description;
        source_form.value = source;
        type_form.value = type;
        color_form.value = color;
        if(error){
            error_form.textContent = "Error: " + error;
            error_form.classList.remove("hidden");
        }
        error_form.classList.add("hidden");
        onTypeChange();
        type_form.addEventListener("change", onTypeChange);
    }

    function onsubmit() {
        try {
            if(!read_form()){
                return false;
            }
            let sane_color = color.trim();
            if (sane_color) {
                let color_match = COLOR_RE.exec(sane_color);
                if (!color_match) {
                    error = "Invalid color";
                    fill_form();
                    return false;
                }
                sane_color = color_match[1];
            }
            let loading_scene = new LoadingScene();
            push_scene(loading_scene);
            let collection = new Collection(href, type, displayname, description, sane_color, 0, 0, source);
            let callback = function(error1) {
                if (scene_index === null) {
                    return;
                }
                create_edit_req = null;
                if (error1) {
                    error = error1;
                    pop_scene(scene_index);
                } else {
                    pop_scene(scene_index - 1);
                }
            };
            if (edit) {
                create_edit_req = edit_collection(user, password, collection, callback);
            } else {
                create_edit_req = create_collection(user, password, collection, callback);
            }
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


    function onTypeChange(e){
        if(type_form.value == CollectionType.WEBCAL){
            source_label.classList.remove("hidden");
            source_form.classList.remove("hidden");
        }else{
            source_label.classList.add("hidden");
            source_form.classList.add("hidden");
        }
    }

    this.show = function() {
        this.release();
        scene_index = scene_stack.length - 1;
        // Clone type_form because it's impossible to hide options without removing them
        saved_type_form = type_form;
        type_form = type_form.cloneNode(true);
        saved_type_form.parentNode.replaceChild(type_form, saved_type_form);
        remove_invalid_types();
        html_scene.classList.remove("hidden");
        if (edit) {
            title_form.textContent = collection.displayname || collection.href;
        }
        fill_form();
        submit_btn.onclick = onsubmit;
        cancel_btn.onclick = oncancel;
        if(error){
            error_form.textContent = "Error: " + error;
            error_form.classList.remove("hidden");
        }else{
            error_form.classList.add("hidden");
        }
    };
    this.hide = function() {
        read_form();
        html_scene.classList.add("hidden");
        // restore type_form
        type_form.parentNode.replaceChild(saved_type_form, type_form);
        type_form = saved_type_form;
        saved_type_form = null;
        submit_btn.onclick = null;
        cancel_btn.onclick = null;
    };
    this.release = function() {
        scene_index = null;
        if (create_edit_req !== null) {
            create_edit_req.abort();
            create_edit_req = null;
        }
    };
}