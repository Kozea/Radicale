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
import { CreateEditCollectionScene } from "./CreateEditCollectionScene.js";
import { CreateShareCollectionScene } from "./ShareCollectionScene.js";
import { UploadCollectionScene } from "./UploadCollectionScene.js";
import { DeleteCollectionScene } from "./DeleteCollectionScene.js";
import { LoadingScene } from "./LoadingScene.js";
import { get_collections } from "./api.js";
import { CollectionType } from "./models.js";
import { bytesToHumanReadable } from "./utils.js";
import { SERVER } from "./constants.js";

/**
 * @constructor
 * @implements {Scene}
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection The principal collection.
 * @param {function(string)} onerror Called when an error occurs, before the
 *                                   scene is popped.
 */
export function CollectionsScene(user, password, collection, onerror) {
    let html_scene = document.getElementById("collectionsscene");
    let template = html_scene.querySelector("[data-name=collectiontemplate]");
    let new_btn = html_scene.querySelector("[data-name=new]");
    let upload_btn = html_scene.querySelector("[data-name=upload]");

    /** @type {?number} */ let scene_index = null;
    /** @type {?XMLHttpRequest} */ let collections_req = null;
    /** @type {?Array<Collection>} */ let collections = null;
    /** @type {Array<Node>} */ let nodes = [];

    function onnew() {
        try {
            let create_collection_scene = new CreateEditCollectionScene(user, password, collection);
            push_scene(create_collection_scene, false);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function onupload() {
        try {
            let upload_scene = new UploadCollectionScene(user, password, collection);
            push_scene(upload_scene);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function onedit(collection) {
        try {
            let edit_collection_scene = new CreateEditCollectionScene(user, password, collection);
            push_scene(edit_collection_scene, false);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function onshare(collection) {
        try {
            let share_collection_scene = new CreateShareCollectionScene(user, password, collection);
            push_scene(share_collection_scene, false);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function ondelete(collection) {
        try {
            let delete_collection_scene = new DeleteCollectionScene(user, password, collection);
            push_scene(delete_collection_scene, false);
        } catch(err) {
            console.error(err);
        }
        return false;
    }

    function show_collections(collections) {
        let heightOfNavBar = document.querySelector("#logoutview").offsetHeight + "px";
        html_scene.style.marginTop = heightOfNavBar;
        html_scene.style.height = "calc(100vh - " + heightOfNavBar +")";
        collections.forEach(function (collection) {
            let node = template.cloneNode(true);
            node.classList.remove("hidden");
            let title_form = node.querySelector("[data-name=title]");
            let description_form = node.querySelector("[data-name=description]");
            let contentcount_form = node.querySelector("[data-name=contentcount]");
            let url_form = node.querySelector("[data-name=url]");
            let color_form = node.querySelector("[data-name=color]");
            let delete_btn = node.querySelector("[data-name=delete]");
            let edit_btn = node.querySelector("[data-name=edit]");
            let share_btn = node.querySelector("[data-name=share]");
            let download_btn = node.querySelector("[data-name=download]");
            if (collection.color) {
                color_form.style.background = collection.color;
            }
            let possible_types = [CollectionType.ADDRESSBOOK, CollectionType.WEBCAL];
            [CollectionType.CALENDAR, ""].forEach(function(e) {
                [CollectionType.union(e, CollectionType.JOURNAL), e].forEach(function(e) {
                    [CollectionType.union(e, CollectionType.TASKS), e].forEach(function(e) {
                        if (e) {
                            possible_types.push(e);
                        }
                    });
                });
            });
            possible_types.forEach(function(e) {
                if (e !== collection.type) {
                    node.querySelector("[data-name=" + e + "]").classList.add("hidden");
                }
            });
            title_form.textContent = collection.displayname || collection.href;
            if(title_form.textContent.length > 30){
                title_form.classList.add("smalltext");
            }
            description_form.textContent = collection.description;
            if(description_form.textContent.length > 150){
                description_form.classList.add("smalltext");
            }
            if(collection.type != CollectionType.WEBCAL){
                let contentcount_form_txt = (collection.contentcount > 0 ? Number(collection.contentcount).toLocaleString() : "No") + " item" + (collection.contentcount == 1 ? "" : "s") + " in collection";
                if(collection.contentcount > 0){
                    contentcount_form_txt += " (" + bytesToHumanReadable(collection.size) + ")";
                }
                contentcount_form.textContent = contentcount_form_txt;
            }
            let href = SERVER + collection.href;
            url_form.value = href;
            download_btn.href = href;
            if(collection.type == CollectionType.WEBCAL){
                download_btn.parentElement.classList.add("hidden");
            }
            delete_btn.onclick = function() {return ondelete(collection);};
            edit_btn.onclick = function() {return onedit(collection);};
            share_btn.onclick = function() {return onshare(collection);};
            node.classList.remove("hidden");
            nodes.push(node);
            template.parentNode.insertBefore(node, template);
        });
    }

    function update() {
        let loading_scene = new LoadingScene();
        push_scene(loading_scene, false);
        collections_req = get_collections(user, password, collection, function(collections1, error) {
            if (scene_index === null) {
                return;
            }
            collections_req = null;
            if (error) {
                onerror(error);
                pop_scene(scene_index - 1);
            } else {
                collections = collections1;
                pop_scene(scene_index);
            }
        });
    }

    this.show = function() {
        html_scene.classList.remove("hidden");
        new_btn.onclick = onnew;
        upload_btn.onclick = onupload;
        if (collections === null) {
            update();
        } else {
            // from update loading scene
            show_collections(collections);
        }
    };
    this.hide = function() {
        html_scene.classList.add("hidden");
        scene_index = scene_stack.length - 1;
        new_btn.onclick = null;
        upload_btn.onclick = null;
        collections = null;
        // remove collection
        nodes.forEach(function(node) {
            node.parentNode.removeChild(node);
        });
        nodes = [];
    };
    this.release = function() {
        scene_index = null;
        if (collections_req !== null) {
            collections_req.abort();
            collections_req = null;
        }
        collections = null;
    };
}