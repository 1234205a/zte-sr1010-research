package main

import (
	"errors"
	"flag"
	"io"
	"log"
	"net"
	"sync"
	"time"
)

func relay(client net.Conn, upstream string, maxLifetime time.Duration) {
	defer client.Close()
	server, err := net.DialTimeout("tcp", upstream, 4*time.Second)
	if err != nil {
		log.Printf("dial %s: %v", upstream, err)
		return
	}
	defer server.Close()
	if maxLifetime > 0 {
		deadline := time.Now().Add(maxLifetime)
		_ = client.SetDeadline(deadline)
		_ = server.SetDeadline(deadline)
	}

	var wg sync.WaitGroup
	wg.Add(2)
	copyHalf := func(dst, src net.Conn) {
		defer wg.Done()
		_, _ = io.Copy(dst, src)
		if tcp, ok := dst.(*net.TCPConn); ok {
			_ = tcp.CloseWrite()
		}
	}
	go copyHalf(server, client)
	go copyHalf(client, server)
	wg.Wait()
}

func serve(listener net.Listener, upstream string, maxLifetime time.Duration) error {
	for {
		client, err := listener.Accept()
		if err != nil {
			return err
		}
		go relay(client, upstream, maxLifetime)
	}
}

func main() {
	listen := flag.String("listen", "192.168.50.1:8088", "local listen address")
	upstream := flag.String("upstream", "192.168.100.1:80", "ONT address")
	maxLifetime := flag.Duration("max-lifetime", 15*time.Minute, "maximum backend connection lifetime")
	flag.Parse()

	listener, err := net.Listen("tcp", *listen)
	if err != nil {
		log.Fatal(err)
	}
	defer listener.Close()
	if err := serve(listener, *upstream, *maxLifetime); err != nil && !errors.Is(err, net.ErrClosed) {
		log.Fatal(err)
	}
}
