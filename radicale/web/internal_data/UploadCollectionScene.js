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

import { Scene, pop_scene, scene_stack } from "./scene_manager.js";
import { Collection } from "./models.js";
import { cleanHREFinput, isValidHREF, random_uuid } from "./utils.js";
import { upload_collection } from "./api.js";

/**
 * @constructor
 * @implements {Scene}
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection parent collection
 * @param {Array<File>} files
 */
export function UploadCollectionScene(user, password, collection) {
    let html_scene = document.getElementById("uploadcollectionscene");
    let template = html_scene.querySelector("[data-name=filetemplate]");
    let upload_btn = html_scene.querySelector("[data-name=submit]");
    let close_btn = html_scene.querySelector("[data-name=close]");
    let uploadfile_form = html_scene.querySelector("[data-name=uploadfile]");
    let uploadfile_lbl = html_scene.querySelector("label[for=uploadfile]");
    let href_form = html_scene.querySelector("[data-name=href]");
    let href_label = html_scene.querySelector("label[for=href]");
    let hreflimitmsg_html = html_scene.querySelector("[data-name=hreflimitmsg]");
    let pending_html = html_scene.querySelector("[data-name=pending]");

    let files = uploadfile_form.files;
    href_form.addEventListener("keydown", cleanHREFinput);
    upload_btn.onclick = upload_start;
    uploadfile_form.onchange = onfileschange;

    href_form.value = "";

    /** @type {?number} */ let scene_index = null;
    /** @type {?XMLHttpRequest} */ let upload_req = null;
    /** @type {Array<string>} */ let results = [];
    /** @type {?Array<Node>} */ let nodes = null;

    function upload_start() {
        try {
            if(!read_form()){
                return false;
            }
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
                let node = template.cloneNode(true);
                node.classList.remove("hidden");
                let name_form = node.querySelector("[data-name=name]");
                name_form.textContent = file.name;
                node.classList.remove("hidden");
                nodes.push(node);
                updateFileStatus(i);
                template.parentNode.insertBefore(node, template);
            }
            upload_next();
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function upload_next(){
        try{
            if (files.length === results.length) {
                pending_html.classList.add("hidden");
                close_btn.classList.remove("hidden");
                return;
            } else {
                let file = files[results.length];
                if(files.length > 1 || href.length == 0){
                    href = random_uuid();
                }
                let upload_href = collection.href + href + "/";
                upload_req = upload_collection(user, password, upload_href, file, function(result) {
                    upload_req = null;
                    results.push(result);
                    updateFileStatus(results.length - 1);
                    upload_next();
                });
            }
        }catch(err){
            console.error(err);
        }
    }

    function onclose() {
        try {
            pop_scene(scene_index - 1);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function updateFileStatus(i) {
        if (nodes === null) {
            return;
        }
        let success_form = nodes[i].querySelector("[data-name=success]");
        let error_form = nodes[i].querySelector("[data-name=error]");
        if (results.length > i) {
            if (results[i]) {
                success_form.classList.add("hidden");
                error_form.textContent = "Error: " + results[i];
                error_form.classList.remove("hidden");
            } else {
              success_form.classList.remove("hidden");
              error_form.classList.add("hidden");
            }
        } else {
            success_form.classList.add("hidden");
            error_form.classList.add("hidden");
        }
    }

    function read_form() {
        cleanHREFinput(href_form);
        let newhreftxtvalue = href_form.value.trim().toLowerCase();
        if(!isValidHREF(newhreftxtvalue)){
            alert("You must enter a valid HREF");
            return false;
        }
        href = newhreftxtvalue;

        if(uploadfile_form.files.length == 0){
            alert("You must select at least one file to upload");
            return false;
        }
        files = uploadfile_form.files;
        return true;
    }

    function onfileschange() {
        files = uploadfile_form.files;
        if(files.length > 1){
            hreflimitmsg_html.classList.remove("hidden");
            href_form.classList.add("hidden");
            href_label.classList.add("hidden");
            href_form.value = random_uuid(); // dummy, will be replaced on upload
        }else{
            hreflimitmsg_html.classList.add("hidden");
            href_form.classList.remove("hidden");
            href_label.classList.remove("hidden");
            href_form.value = files[0].name.replace(/\.(ics|vcf)$/, '');
        }
        return false;
    }

    this.show = function() {
        scene_index = scene_stack.length - 1;
        html_scene.classList.remove("hidden");
        close_btn.onclick = onclose;
        if(error){
            error_form.textContent = "Error: " + error;
            error_form.classList.remove("hidden");
        }else{
            error_form.classList.add("hidden");
        }
    };

    this.hide = function() {
        html_scene.classList.add("hidden");
        close_btn.classList.remove("hidden");
        upload_btn.classList.remove("hidden");
        uploadfile_form.classList.remove("hidden");
        uploadfile_lbl.classList.remove("hidden");
        href_form.classList.remove("hidden");
        href_label.classList.remove("hidden");
        hreflimitmsg_html.classList.add("hidden");
        pending_html.classList.add("hidden");
        close_btn.onclick = null;
        upload_btn.onclick = null;
        href_form.value = "";
        uploadfile_form.value = "";
        if(nodes == null){
            return;
        }
        nodes.forEach(function(node) {
            node.parentNode.removeChild(node);
        });
        nodes = null;
    };
    this.release = function() {
        scene_index = null;
        if (upload_req !== null) {
            upload_req.abort();
            upload_req = null;
        }
    };
}