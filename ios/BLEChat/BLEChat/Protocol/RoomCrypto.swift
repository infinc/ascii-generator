//  RoomCrypto.swift
//  部屋IDとパスワードから、広告に載せる識別子と共有秘密を作る。
//
//  Python 版 ble_link.py の room_secret / room_id_hex / service_uuid /
//  advert_name と1バイトも違わない値を返す必要がある。ここがずれると
//  スキャンの段階でお互いを見つけられない。

import CoreBluetooth
import CryptoKit
import Foundation

enum RoomCrypto {

    /// Central -> Peripheral。ゲストからホストへの送信に使う。
    static let rxCharUUID = CBUUID(string: "6E5F0001-8A2B-4C3D-9E1F-A5B6C7D8E9F0")
    /// Peripheral -> Central。ホストから全ゲストへの通知に使う。
    static let txCharUUID = CBUUID(string: "6E5F0002-8A2B-4C3D-9E1F-A5B6C7D8E9F0")

    /// ホストの送信者タグは固定。
    static let hostSrc: UInt16 = 0

    /// 部屋ID とパスワードから共有秘密を作る。
    static func secret(roomName: String, roomPassword: String) -> [UInt8] {
        let source = "\(roomName)::\(roomPassword)"
        return Array(SHA256.hash(data: Data(source.utf8)))
    }

    /// Achex 版の real_room_id と同じ値。メッセージの "to" に入れる。
    static func roomIdHex(roomName: String, roomPassword: String) -> String {
        hex(secret(roomName: roomName, roomPassword: roomPassword))
    }

    /// 部屋ごとの Service UUID。
    ///
    /// 部屋IDとパスワードの両方が一致したときだけ同じ UUID になるので、
    /// 違う部屋のホストはスキャンの段階で候補に上がらない。
    static func serviceUUID(roomName: String, roomPassword: String) -> CBUUID {
        let b = secret(roomName: roomName, roomPassword: roomPassword)
        // Python の uuid.UUID(bytes=...) と同じ並び (先頭16バイトをそのまま)。
        let raw = (b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7],
                   b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15])
        return CBUUID(nsuuid: UUID(uuid: raw))
    }

    /// アドバタイズに載せる名前 (6文字)。
    ///
    /// アドバタイズは31バイトしかなく、Flags(3) + 128bit Service UUID(18) で
    /// 既に21バイト使う。6文字にして2バイトの余白を残している。
    static func advertName(roomName: String, roomPassword: String) -> String {
        "A" + roomIdHex(roomName: roomName, roomPassword: roomPassword).prefix(5)
    }

    static func hex(_ bytes: [UInt8]) -> String {
        bytes.map { String(format: "%02x", $0) }.joined()
    }
}
