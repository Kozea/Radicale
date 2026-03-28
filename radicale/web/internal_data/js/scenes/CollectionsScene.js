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

import { delete_collection } from "../api/api.js";
import { get_auth_header } from "../api/common.js";
import { SERVER } from "../constants.js";
import { Collection, CollectionType } from "../models/collection.js";
import { collectionsCache } from "../utils/collections_cache.js";
import { ErrorHandler } from "../utils/error.js";
import { bytesToHumanReadable, get_element, get_element_by_id } from "../utils/misc.js";
import { CreateEditCollectionScene } from "./CreateEditCollectionScene.js";
import { DeleteConfirmationScene } from "./DeleteConfirmationScene.js";
import { IncomingSharingScene } from "./IncomingSharingScene.js";
import { Scene, push_scene } from "./scene_manager.js";
import { ShareCollectionScene, maybe_enable_sharing_options } from "./ShareCollectionScene.js";
import { UploadCollectionScene } from "./UploadCollectionScene.js";

/**
 * @implements {Scene}
 */
export class CollectionsScene {
    /**
     * @param {string} user
     * @param {?string} password
     * @param {Collection} principal_collection The princial collection
     * @param {function(?string):void} onerror Called when an error occurs, before the
     *                                   scene is popped.
     */
    constructor(user, password, principal_collection, onerror) {
        /** @type {HTMLElement} */ let html_scene = get_element_by_id("collectionsscene");
        /** @type {HTMLElement} */ let template = get_element(html_scene, "[data-name=collectiontemplate]");
        /** @type {HTMLElement} */ let new_btn = get_element(html_scene, "[data-name=new]");
        /** @type {HTMLElement} */ let upload_btn = get_element(html_scene, "[data-name=upload]");
        /** @type {HTMLElement} */ let incomingshares_btn = get_element(html_scene, "[data-name=incomingshares]");
        /** @type {HTMLElement} */ let error_div = get_element(html_scene, "[data-name=collectionsscene_error]");

        /** @type {Array<HTMLElement>} */ let nodes = [];
        let errorHandler = new ErrorHandler(error_div);

        function onnew() {
            try {
                let create_collection_scene = new CreateEditCollectionScene(user, password, principal_collection);
                push_scene(create_collection_scene);
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        function onupload() {
            try {
                let upload_scene = new UploadCollectionScene(user, password, principal_collection);
                push_scene(upload_scene);
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        function onincomingshares() {
            try {
                let incoming_sharing_scene = new IncomingSharingScene(user, password);
                push_scene(incoming_sharing_scene);
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        /**
         * @param {Collection} collection
         */
        function onedit(collection) {
            try {
                let edit_collection_scene = new CreateEditCollectionScene(user, password, collection);
                push_scene(edit_collection_scene);
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        /**
         * @param {Collection} collection
         */
        function onshare(collection) {
            try {
                let share_collection_scene = new ShareCollectionScene(user, password, collection);
                push_scene(share_collection_scene);
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        /**
         * @param {Collection} collection
         */
        function ondelete(collection) {
            try {
                let delete_collection_scene = new DeleteConfirmationScene(
                    user, password, "Delete Collection", collection, collection.displayname || collection.href,
                    delete_collection, true
                );
                push_scene(delete_collection_scene);
            } catch (err) {
                console.error(err);
            }
            return false;
        }

        /**
         * @param {any[]} collections
         * @param {import("../api/sharing.js").Share[]} shares
         * @param {boolean} clear_error
         */
        function show_collections(collections, shares, clear_error) {
            /** @type {HTMLElement} */ let navBar = get_element(document, "#logoutview");
            let heightOfNavBar = navBar.offsetHeight + "px";
            html_scene.style.marginTop = heightOfNavBar;
            html_scene.style.height = "calc(100vh - " + heightOfNavBar + ")";

            if (clear_error) {
                errorHandler.clearError();
            }

            // Clear old nodes
            nodes.forEach(function (node) {
                if (node.parentNode) {
                    node.parentNode.removeChild(node);
                }
            });
            nodes = [];

            collections.forEach(function (/** @type {Collection} */ collection) {
                /** @type {HTMLElement} */ let node = /** @type {HTMLElement} */(template.cloneNode(true));
                node.classList.remove("hidden");
                /** @type {HTMLElement} */ let title_form = get_element(node, "[data-name=title]");
                /** @type {HTMLElement} */ let description_form = get_element(node, "[data-name=description]");
                /** @type {HTMLElement} */ let contentcount_form = get_element(node, "[data-name=contentcount]");
                /** @type {HTMLInputElement} */ let url_form = /** @type {HTMLInputElement} */ (get_element(node, "[data-name=url]"));
                /** @type {HTMLElement} */ let color_form = get_element(node, "[data-name=color]");
                /** @type {HTMLElement} */ let delete_btn = get_element(node, "[data-name=delete]");
                /** @type {HTMLElement} */ let edit_btn = get_element(node, "[data-name=edit]");
                /** @type {HTMLElement} */ let share_btn = get_element(node, "[data-name=share]");
                /** @type {HTMLAnchorElement} */ let download_btn = /** @type {HTMLAnchorElement} */ (get_element(node, "[data-name=download]"));
                if (collection.color) {
                    color_form.style.background = collection.color;
                }
                let possible_types = [CollectionType.ADDRESSBOOK, CollectionType.WEBCAL];
                [CollectionType.CALENDAR, ""].forEach(function (e) {
                    [CollectionType.union(e, CollectionType.JOURNAL), e].forEach(function (e) {
                        [CollectionType.union(e, CollectionType.TASKS), e].forEach(function (e) {
                            if (e) {
                                possible_types.push(e);
                            }
                        });
                    });
                });
                possible_types.forEach(function (e) {
                    if (e !== collection.type) {
                        get_element(node, "[data-name=" + e + "]").classList.add("hidden");
                    }
                });
                let share_info = get_element(node, "[data-name=shared-by]");
                let transformed_from = get_element(node, "[data-name=transformed-from]");
                let share = (shares || []).find(
                    // TODO: Eventually remove the check for "bday"
                    s => (s.ShareType === "map" || s.ShareType === "bday") &&
                        (s.PathOrToken || "").replace(/\/+$/, "") === (collection.href || "").replace(/\/+$/, ""));
                if (share) {
                    if (share.Owner !== user) {
                        share_info.classList.remove("hidden");
                        get_element(node, "[data-name=shared-by-owner]").textContent = share.Owner;
                    } else {
                        transformed_from.classList.remove("hidden");
                    }
                    let share_option = get_element(node, "[data-name=shareoption]");
                    if (share_option) {
                        share_option.classList.add("hidden");
                        share_option.removeAttribute("data-name");
                    }
                    delete_btn.classList.add("hidden");
                    if (!/w/i.test(share.Permissions || "")) {
                        edit_btn.classList.add("hidden");
                    } else {
                        edit_btn.classList.remove("hidden");
                    }
                }
                title_form.textContent = collection.displayname || collection.href;
                if (title_form.textContent.length > 30) {
                    title_form.classList.add("smalltext");
                }
                description_form.textContent = collection.description;
                if (description_form.textContent.length > 150) {
                    description_form.classList.add("smalltext");
                }
                if (collection.type != CollectionType.WEBCAL) {
                    let contentcount_form_txt = (collection.contentcount > 0 ? Number(collection.contentcount).toLocaleString() : "No") + " item" + (collection.contentcount == 1 ? "" : "s") + " in collection";
                    if (collection.contentcount > 0) {
                        contentcount_form_txt += " (" + bytesToHumanReadable(collection.size) + ")";
                    }
                    contentcount_form.textContent = contentcount_form_txt;
                }
                let href = SERVER + collection.href;
                url_form.value = href;
                download_btn.href = href;
                download_btn.onclick = function (event) {
                    event.preventDefault();
                    let auth = get_auth_header(user, password);
                    let headers = auth ? {
                        'Authorization': auth
                    } : undefined;
                    fetch(href, { headers: headers }).then(function (response) {
                        if (response.ok) {
                            return response.blob();
                        }
                        throw new Error("Download failed: " + response.statusText);
                    }).then(function (blob) {
                        let url = window.URL.createObjectURL(blob);
                        let a = document.createElement("a");
                        a.href = url;
                        a.download = (collection.displayname || collection.href).replace(/\/+$/, "") + (collection.type === CollectionType.ADDRESSBOOK ? ".vcf" : ".ics");
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        window.URL.revokeObjectURL(url);
                    })["catch"](function (error) {
                        errorHandler.setError(error.message);
                    });
                };
                if (collection.type == CollectionType.WEBCAL) {
                    if (download_btn.parentElement) {
                        download_btn.parentElement.classList.add("hidden");
                    }
                }
                delete_btn.onclick = function () { return ondelete(collection); };
                edit_btn.onclick = function () { return onedit(collection); };
                share_btn.onclick = function () { return onshare(collection); };
                node.classList.remove("hidden");
                nodes.push(node);
                if (template.parentNode) {
                    template.parentNode.insertBefore(node, template);
                }
            });
        }

        this.errorwrapper = function (/** @type {string} */ error) {
            errorHandler.setError(error);
            if (onerror) onerror(error);
        };

        this.show = function () {
            html_scene.classList.remove("hidden");
            new_btn.onclick = onnew;
            upload_btn.onclick = onupload;
            incomingshares_btn.onclick = onincomingshares;
            collectionsCache.getChildCollections(user, password, principal_collection, this.errorwrapper, show_collections);
            collectionsCache.getServerFeatures(user, password, this.errorwrapper, maybe_enable_sharing_options);
        };
        this.hide = function () {
            html_scene.classList.add("hidden");
            new_btn.onclick = null;
            upload_btn.onclick = null;
            incomingshares_btn.onclick = null;
            // remove collection
            nodes.forEach(function (node) {
                if (node.parentNode) {
                    node.parentNode.removeChild(node);
                }
            });
            nodes = [];
        };
        this.release = function () {
        };
    }
}