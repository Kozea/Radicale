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
import { Collection, CollectionType, Permission } from "../models/collection.js";
import { collectionsCache } from "../utils/collections_cache.js";
import { ErrorHandler } from "../utils/error.js";
import { bytesToHumanReadable, get_element, get_element_by_id } from "../utils/misc.js";
import { UrlTextHandler } from "../utils/url_text.js";
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
        this._user = user;
        this._password = password;
        this._principal_collection = principal_collection;
        this._onerror = onerror;

        this._html_scene = get_element_by_id("collectionsscene");
        this._template = get_element(this._html_scene, "[data-name=collectiontemplate]");
        this._new_btn = get_element(this._html_scene, "[data-name=new]");
        this._upload_btn = get_element(this._html_scene, "[data-name=upload]");
        this._incomingshares_btn = get_element(this._html_scene, "[data-name=incomingshares]");
        this._error_div = get_element(this._html_scene, "[data-name=collectionsscene_error]");

        /** @type {Array<HTMLElement>} */ this._nodes = [];
        this._errorHandler = new ErrorHandler(this._error_div);
    }

    _onnew() {
        try {
            let create_collection_scene = new CreateEditCollectionScene(this._user, this._password, this._principal_collection);
            push_scene(create_collection_scene);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    _onupload() {
        try {
            let upload_scene = new UploadCollectionScene(this._user, this._password, this._principal_collection);
            push_scene(upload_scene);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    _onincomingshares() {
        try {
            let incoming_sharing_scene = new IncomingSharingScene(this._user, this._password);
            push_scene(incoming_sharing_scene);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    /**
     * @param {Collection} collection
     */
    _onedit(collection) {
        try {
            let edit_collection_scene = new CreateEditCollectionScene(this._user, this._password, collection);
            push_scene(edit_collection_scene);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    /**
     * @param {Collection} collection
     */
    _onshare(collection) {
        try {
            let share_collection_scene = new ShareCollectionScene(this._user, this._password, collection);
            push_scene(share_collection_scene);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    /**
     * @param {Collection} collection
     */
    _ondelete(collection) {
        try {
            let delete_collection_scene = new DeleteConfirmationScene(
                this._user, this._password, "Delete Collection", collection, collection.displayname || collection.href,
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
    _show_collections(collections, shares, clear_error) {
        /** @type {HTMLElement} */ let navBar = get_element(document, "#logoutview");
        let heightOfNavBar = navBar.offsetHeight + "px";
        this._html_scene.style.marginTop = heightOfNavBar;
        this._html_scene.style.height = "calc(100vh - " + heightOfNavBar + ")";

        if (clear_error) {
            this._errorHandler.clearError();
        }

        // Clear old nodes
        this._nodes.forEach(function (node) {
            if (node.parentNode) {
                node.parentNode.removeChild(node);
            }
        });
        this._nodes = [];

        collections.forEach((/** @type {Collection} */ collection) => {
            /** @type {HTMLElement} */ let node = /** @type {HTMLElement} */(this._template.cloneNode(true));
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
            /** @type {HTMLButtonElement} */ let copy_btn = /** @type {HTMLButtonElement} */ (get_element(node, "[data-name=copy-url]"));
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

            let share_option = get_element(node, "[data-name=shareoption]");
            let can_share = collection.has_permission(Permission.SHARE_MAP) || collection.has_permission(Permission.SHARE_TOKEN);
            if (share_option) {
                if (can_share) {
                    share_option.classList.remove("hidden");
                } else {
                    share_option.classList.add("hidden");
                }
            }

            let share_info = get_element(node, "[data-name=shared-by]");
            let transformed_from = get_element(node, "[data-name=transformed-from]");
            let share = (shares || []).find(
                s => (s.ShareType === "map") &&
                    (s.PathOrToken || "").replace(/\/+$/, "") === (collection.href || "").replace(/\/+$/, ""));
            if (share) {
                if (share.Owner !== this._user) {
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
            let href = collection.href;
            new UrlTextHandler(url_form, copy_btn).setHref(href);
            download_btn.href = href;
            download_btn.onclick = (event) => {
                event.preventDefault();
                let auth = get_auth_header(this._user, this._password);
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
                })["catch"]((error) => {
                    this._errorHandler.setError(error.message);
                });
            };
            if (collection.type == CollectionType.WEBCAL) {
                if (download_btn.parentElement) {
                    download_btn.parentElement.classList.add("hidden");
                }
            }
            delete_btn.onclick = () => { return this._ondelete(collection); };
            edit_btn.onclick = () => { return this._onedit(collection); };
            share_btn.onclick = () => { return this._onshare(collection); };
            node.classList.remove("hidden");
            this._nodes.push(node);
            if (this._template.parentNode) {
                this._template.parentNode.insertBefore(node, this._template);
            }
        });
    }

    _errorwrapper(/** @type {string} */ error) {
        this._errorHandler.setError(error);
        if (this._onerror) this._onerror(error);
    }

    show() {
        this._html_scene.classList.remove("hidden");
        this._new_btn.onclick = () => this._onnew();
        this._upload_btn.onclick = () => this._onupload();
        this._incomingshares_btn.onclick = () => this._onincomingshares();
        collectionsCache.getChildCollections(this._user, this._password, this._principal_collection, (e) => this._errorwrapper(e), (c, s, ce) => this._show_collections(c, s, ce));
        collectionsCache.getServerFeatures(this._user, this._password, (e) => this._errorwrapper(e), maybe_enable_sharing_options);
    }

    hide() {
        this._html_scene.classList.add("hidden");
        this._new_btn.onclick = null;
        this._upload_btn.onclick = null;
        this._incomingshares_btn.onclick = null;
        // remove collection
        this._nodes.forEach(function (node) {
            if (node.parentNode) {
                node.parentNode.removeChild(node);
            }
        });
        this._nodes = [];
    }

    release() {
    }

    is_transient() { return false; }
}