package com.werdeil.lyrioncustomdata

import java.io.ByteArrayOutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException

/**
 * Discovers Lyrion Music Server instances on the local network using the
 * same UDP protocol as lms-material-app: a broadcast request on port 3483
 * ('e' + TLV tags), answered unicast by each server ('E' + TLV values).
 *
 * Lyrion Custom Data itself has no discovery protocol, but it normally runs
 * on the same host as Lyrion, so the discovered address is used to suggest
 * a dashboard URL on the app's default port.
 */
object ServerDiscovery {

    data class Server(val host: String, val name: String)

    private const val DISCOVERY_PORT = 3483
    private const val TOTAL_TIMEOUT_MS = 2500L
    private const val RECEIVE_TIMEOUT_MS = 500

    /** Blocking call; run it off the main thread. */
    fun discover(): List<Server> {
        val servers = LinkedHashMap<String, Server>()
        DatagramSocket().use { socket ->
            socket.broadcast = true
            socket.soTimeout = RECEIVE_TIMEOUT_MS

            val request = buildRequest()
            socket.send(
                DatagramPacket(
                    request,
                    request.size,
                    InetAddress.getByName("255.255.255.255"),
                    DISCOVERY_PORT
                )
            )

            val deadline = System.currentTimeMillis() + TOTAL_TIMEOUT_MS
            val buffer = ByteArray(1024)
            while (System.currentTimeMillis() < deadline) {
                val response = DatagramPacket(buffer, buffer.size)
                try {
                    socket.receive(response)
                } catch (e: SocketTimeoutException) {
                    continue
                }
                parseResponse(response)?.let { servers[it.host] = it }
            }
        }
        return servers.values.toList()
    }

    private fun buildRequest(): ByteArray {
        val out = ByteArrayOutputStream()
        out.write('e'.code)
        for (tag in listOf("NAME", "JSON")) {
            out.write(tag.toByteArray(Charsets.US_ASCII))
            out.write(0) // no payload in the request, just the tag
        }
        return out.toByteArray()
    }

    private fun parseResponse(packet: DatagramPacket): Server? {
        val data = packet.data
        val length = packet.length
        if (length < 1 || data[0] != 'E'.code.toByte()) {
            return null
        }
        var name: String? = null
        var i = 1
        while (i + 5 <= length) {
            val tag = String(data, i, 4, Charsets.US_ASCII)
            val valueLength = data[i + 4].toInt() and 0xff
            if (i + 5 + valueLength > length) {
                break
            }
            if (tag == "NAME") {
                name = String(data, i + 5, valueLength, Charsets.UTF_8)
            }
            i += 5 + valueLength
        }
        val host = packet.address.hostAddress ?: return null
        return Server(host, name ?: host)
    }
}
