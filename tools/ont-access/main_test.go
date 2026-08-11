package main

import (
	"io"
	"net"
	"testing"
	"time"
)

func TestRelay(t *testing.T) {
	upstream, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer upstream.Close()
	go func() {
		conn, err := upstream.Accept()
		if err == nil {
			defer conn.Close()
			_, _ = io.Copy(conn, conn)
		}
	}()

	proxy, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer proxy.Close()
	go func() { _ = serve(proxy, upstream.Addr().String(), 100*time.Millisecond) }()

	client, err := net.DialTimeout("tcp", proxy.Addr().String(), time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()
	_ = client.SetDeadline(time.Now().Add(time.Second))
	if _, err := client.Write([]byte("ont-ok")); err != nil {
		t.Fatal(err)
	}
	got := make([]byte, len("ont-ok"))
	if _, err := io.ReadFull(client, got); err != nil {
		t.Fatal(err)
	}
	if string(got) != "ont-ok" {
		t.Fatalf("got %q", got)
	}

	time.Sleep(200 * time.Millisecond)
	_ = client.SetDeadline(time.Now().Add(time.Second))
	_, _ = client.Write([]byte("expired"))
	if _, err := client.Read(make([]byte, 1)); err == nil {
		t.Fatal("connection remained open past max lifetime")
	}
}
